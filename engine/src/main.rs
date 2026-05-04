//! TradePilot Execution Engine — Rust
//!
//! Type-safe order execution, risk management, and position tracking.
//! Receives signals from Python scoring layer, validates through risk gates,
//! and executes safely via Zerodha Kite API.

mod orders;
mod risk;
mod positions;

use actix_web::{web, App, HttpServer, HttpResponse};
use actix_cors::Cors;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

use orders::{OrderBuilder, Direction};
use risk::{RiskConfig, RiskManager};
use positions::PositionManager;

/// Shared application state
struct AppState {
    risk_manager: Mutex<RiskManager>,
    position_manager: Mutex<PositionManager>,
}

/// Signal from Python scoring layer
#[derive(Debug, Deserialize)]
struct TradeSignal {
    symbol: String,
    direction: String,
    score: f64,
    entry_price: f64,
    stop_loss: f64,
    target: f64,
    quantity: u32,
    pool: String,
    tag: Option<String>,
}

#[derive(Serialize)]
struct ApiResponse {
    success: bool,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    data: Option<serde_json::Value>,
}

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(ApiResponse {
        success: true,
        message: "TradePilot Engine v0.1.0 — Rust".into(),
        data: None,
    })
}

async fn execute_signal(
    state: web::Data<AppState>,
    signal: web::Json<TradeSignal>,
) -> HttpResponse {
    let sig = signal.into_inner();

    let direction = match sig.direction.to_uppercase().as_str() {
        "BUY" => Direction::Long,
        "SELL" => Direction::Short,
        _ => return HttpResponse::BadRequest().json(ApiResponse {
            success: false,
            message: format!("Invalid direction: {}", sig.direction),
            data: None,
        }),
    };

    let order = match OrderBuilder::new(&sig.symbol, direction)
        .quantity(sig.quantity)
        .price(rust_decimal::Decimal::try_from(sig.entry_price).unwrap_or_default())
        .stop_loss(rust_decimal::Decimal::try_from(sig.stop_loss).unwrap_or_default())
        .target(rust_decimal::Decimal::try_from(sig.target).unwrap_or_default())
        .tag(sig.tag.as_deref().unwrap_or(&format!("{}-{}", sig.pool, sig.symbol)))
        .build()
    {
        Ok(order) => order,
        Err(e) => return HttpResponse::BadRequest().json(ApiResponse {
            success: false,
            message: format!("Order validation failed: {}", e),
            data: None,
        }),
    };

    let rm = state.risk_manager.lock().unwrap();
    if let Err(rejection) = rm.check_order(&order) {
        return HttpResponse::Forbidden().json(ApiResponse {
            success: false,
            message: format!("Risk rejected: {}", rejection),
            data: None,
        });
    }
    drop(rm);

    // TODO: Place order via Kite API — currently simulated
    let order_id = format!("SIM-{}", order.id);

    let position = positions::Position {
        id: order.id,
        symbol: order.symbol.clone(),
        direction: order.direction,
        quantity: order.quantity,
        entry_price: order.price,
        current_price: order.price,
        stop_loss: order.stop_loss,
        target: order.target,
        trailing_active: false,
        peak_price: order.price,
        trough_price: order.price,
        pnl: dec!(0),
        pnl_pct: dec!(0),
        pool: sig.pool,
        opened_at: chrono::Utc::now(),
        order_id: order_id.clone(),
        sl_order_id: None,
    };

    let order_value = rust_decimal::Decimal::from(order.quantity) * order.price;
    state.risk_manager.lock().unwrap().record_position_opened(&order.symbol, order_value);
    state.position_manager.lock().unwrap().open_position(position);

    HttpResponse::Ok().json(ApiResponse {
        success: true,
        message: format!("Order placed: {} {} x{} @{}",
            if direction == Direction::Long { "LONG" } else { "SHORT" },
            order.symbol, order.quantity, order.price),
        data: Some(serde_json::json!({
            "order_id": order_id,
            "symbol": order.symbol,
            "direction": format!("{:?}", direction),
            "quantity": order.quantity,
            "price": order.price.to_string(),
            "stop_loss": order.stop_loss.to_string(),
        })),
    })
}

async fn risk_status(state: web::Data<AppState>) -> HttpResponse {
    let rm = state.risk_manager.lock().unwrap();
    HttpResponse::Ok().json(rm.status())
}

async fn get_positions(state: web::Data<AppState>) -> HttpResponse {
    let pm = state.position_manager.lock().unwrap();
    HttpResponse::Ok().json(serde_json::json!({
        "open": pm.open_positions(),
        "closed_today": pm.closed_trades(),
        "unrealized_pnl": pm.unrealized_pnl().to_string(),
        "realized_pnl": pm.realized_pnl().to_string(),
    }))
}

#[derive(Debug, Deserialize)]
struct SyncRequest {
    total_positions: u32,
    positions_by_symbol: std::collections::HashMap<String, u32>,
    total_deployed: f64,
}

async fn sync_positions(
    state: web::Data<AppState>,
    req: web::Json<SyncRequest>,
) -> HttpResponse {
    let r = req.into_inner();
    let total_deployed = rust_decimal::Decimal::try_from(r.total_deployed).unwrap_or_default();
    let (old_count, new_count) = state
        .risk_manager
        .lock()
        .unwrap()
        .sync_positions(r.total_positions, r.positions_by_symbol, total_deployed);

    if old_count != new_count {
        tracing::warn!(
            "POSITION DRIFT CORRECTED: Rust had {} positions, Python reports {}",
            old_count, new_count
        );
    }

    HttpResponse::Ok().json(ApiResponse {
        success: true,
        message: format!(
            "Synced: Rust {} -> Python {} ({})",
            old_count,
            new_count,
            if old_count == new_count { "no drift" } else { "drift corrected" }
        ),
        data: Some(serde_json::json!({
            "previous_count": old_count,
            "new_count": new_count,
            "drift_corrected": old_count != new_count,
        })),
    })
}

async fn kill_switch(state: web::Data<AppState>) -> HttpResponse {
    let mut rm = state.risk_manager.lock().unwrap();
    rm.activate_kill_switch("Manual emergency stop via API".into());
    HttpResponse::Ok().json(ApiResponse {
        success: true,
        message: "KILL SWITCH ACTIVATED — all trading stopped".into(),
        data: None,
    })
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "tradepilot_engine=info,actix_web=info".parse().unwrap()),
        )
        .init();

    dotenvy::dotenv().ok();
    let config = RiskConfig::default();
    tracing::info!("TradePilot Engine v0.1.0");
    tracing::info!("Capital: Rs {} | Max loss: Rs {} | Max order: Rs {} | Kill at: {}",
        config.total_capital, config.max_daily_loss, config.max_order_value, config.force_exit_time);

    let state = web::Data::new(AppState {
        risk_manager: Mutex::new(RiskManager::new(config)),
        position_manager: Mutex::new(PositionManager::new()),
    });

    tracing::info!("Server: http://localhost:8080");

    HttpServer::new(move || {
        let cors = Cors::default()
            .allowed_origin("http://localhost:5050")
            .allowed_origin("http://127.0.0.1:5050")
            .allow_any_method()
            .allow_any_header();

        App::new()
            .wrap(cors)
            .app_data(state.clone())
            .route("/health", web::get().to(health))
            .route("/api/execute", web::post().to(execute_signal))
            .route("/api/risk", web::get().to(risk_status))
            .route("/api/positions", web::get().to(get_positions))
            .route("/api/kill", web::post().to(kill_switch))
            .route("/api/risk/sync", web::post().to(sync_positions))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
