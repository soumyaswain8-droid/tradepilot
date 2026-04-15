//! Position management — tracks all open positions with type-safe state transitions.

use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::orders::Direction;

/// A live position in the portfolio
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub id: Uuid,
    pub symbol: String,
    pub direction: Direction,
    pub quantity: u32,
    pub entry_price: Decimal,
    pub current_price: Decimal,
    pub stop_loss: Decimal,
    pub target: Decimal,
    pub trailing_active: bool,
    pub peak_price: Decimal,      // Highest since entry (for LONG trailing)
    pub trough_price: Decimal,    // Lowest since entry (for SHORT trailing)
    pub pnl: Decimal,
    pub pnl_pct: Decimal,
    pub pool: String,
    pub opened_at: DateTime<Utc>,
    pub order_id: String,         // Kite order ID
    pub sl_order_id: Option<String>, // Kite SL order ID (server-side SL)
}

/// Why a position was closed
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CloseReason {
    Target,
    StopLoss,
    TrailingStop,
    SignalFlip,
    TimeExit,       // Force close at 15:15
    KillSwitch,     // Emergency stop
    Manual,         // User-initiated
}

/// A closed trade record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClosedTrade {
    pub id: Uuid,
    pub symbol: String,
    pub direction: Direction,
    pub quantity: u32,
    pub entry_price: Decimal,
    pub exit_price: Decimal,
    pub pnl: Decimal,
    pub pnl_pct: Decimal,
    pub pool: String,
    pub reason: CloseReason,
    pub opened_at: DateTime<Utc>,
    pub closed_at: DateTime<Utc>,
    pub entry_order_id: String,
    pub exit_order_id: String,
}

/// Position manager — owns all open positions
#[derive(Debug, Default)]
pub struct PositionManager {
    positions: Vec<Position>,
    closed_trades: Vec<ClosedTrade>,
}

/// Trailing stop configuration
const TRAILING_TRIGGER_PCT: Decimal = dec!(1.0);   // Activate at +1%
const TRAILING_STEP_PCT: Decimal = dec!(0.5);      // Trail by 0.5%

impl PositionManager {
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a new position
    pub fn open_position(&mut self, position: Position) {
        tracing::info!(
            "OPEN {} {} x{} @{} SL:{} TGT:{} [{}]",
            if position.direction == Direction::Long { "LONG" } else { "SHORT" },
            position.symbol, position.quantity, position.entry_price,
            position.stop_loss, position.target, position.pool
        );
        self.positions.push(position);
    }

    /// Update all positions with current prices. Returns list of positions to close.
    pub fn scan_positions(&mut self, prices: &std::collections::HashMap<String, Decimal>) -> Vec<(usize, CloseReason)> {
        let mut to_close = Vec::new();

        for (idx, pos) in self.positions.iter_mut().enumerate() {
            let Some(&price) = prices.get(&pos.symbol) else { continue };
            pos.current_price = price;

            // Calculate P&L
            match pos.direction {
                Direction::Long => {
                    pos.pnl = (price - pos.entry_price) * Decimal::from(pos.quantity);
                    pos.pnl_pct = (price - pos.entry_price) / pos.entry_price * dec!(100);
                    if price > pos.peak_price { pos.peak_price = price; }
                }
                Direction::Short => {
                    pos.pnl = (pos.entry_price - price) * Decimal::from(pos.quantity);
                    pos.pnl_pct = (pos.entry_price - price) / pos.entry_price * dec!(100);
                    if price < pos.trough_price { pos.trough_price = price; }
                }
            }

            // Check exit conditions
            match pos.direction {
                Direction::Long => {
                    if price <= pos.stop_loss {
                        to_close.push((idx, if pos.trailing_active { CloseReason::TrailingStop } else { CloseReason::StopLoss }));
                    } else if price >= pos.target {
                        to_close.push((idx, CloseReason::Target));
                    } else if pos.pnl_pct >= TRAILING_TRIGGER_PCT && !pos.trailing_active {
                        pos.trailing_active = true;
                        pos.stop_loss = pos.entry_price; // Move SL to breakeven
                        tracing::info!("{}: TRAILING activated -> SL@{}", pos.symbol, pos.entry_price);
                    } else if pos.trailing_active {
                        let trail = pos.peak_price * (dec!(1) - TRAILING_STEP_PCT / dec!(100));
                        if trail > pos.stop_loss { pos.stop_loss = trail.round_dp(2); }
                    }
                }
                Direction::Short => {
                    if price >= pos.stop_loss {
                        to_close.push((idx, if pos.trailing_active { CloseReason::TrailingStop } else { CloseReason::StopLoss }));
                    } else if price <= pos.target {
                        to_close.push((idx, CloseReason::Target));
                    } else if pos.pnl_pct >= TRAILING_TRIGGER_PCT && !pos.trailing_active {
                        pos.trailing_active = true;
                        pos.stop_loss = pos.entry_price;
                        tracing::info!("{}: SHORT TRAILING activated -> SL@{}", pos.symbol, pos.entry_price);
                    } else if pos.trailing_active {
                        let trail = pos.trough_price * (dec!(1) + TRAILING_STEP_PCT / dec!(100));
                        if trail < pos.stop_loss { pos.stop_loss = trail.round_dp(2); }
                    }
                }
            }
        }

        to_close
    }

    /// Close a position and record the trade
    pub fn close_position(&mut self, idx: usize, exit_price: Decimal, reason: CloseReason, exit_order_id: &str) -> Option<ClosedTrade> {
        if idx >= self.positions.len() { return None; }
        let pos = self.positions.remove(idx);

        let pnl = match pos.direction {
            Direction::Long => (exit_price - pos.entry_price) * Decimal::from(pos.quantity),
            Direction::Short => (pos.entry_price - exit_price) * Decimal::from(pos.quantity),
        };
        let pnl_pct = match pos.direction {
            Direction::Long => (exit_price - pos.entry_price) / pos.entry_price * dec!(100),
            Direction::Short => (pos.entry_price - exit_price) / pos.entry_price * dec!(100),
        };

        let trade = ClosedTrade {
            id: pos.id,
            symbol: pos.symbol.clone(),
            direction: pos.direction,
            quantity: pos.quantity,
            entry_price: pos.entry_price,
            exit_price,
            pnl: pnl.round_dp(2),
            pnl_pct: pnl_pct.round_dp(2),
            pool: pos.pool,
            reason,
            opened_at: pos.opened_at,
            closed_at: Utc::now(),
            entry_order_id: pos.order_id,
            exit_order_id: exit_order_id.to_string(),
        };

        let tag = if trade.pnl > Decimal::ZERO { "WIN" } else { "LOSS" };
        tracing::info!(
            "CLOSE {} {} x{} @{} P&L:Rs {} ({:+.2}%) [{}]",
            tag, trade.symbol, trade.quantity, exit_price,
            trade.pnl, trade.pnl_pct, trade.reason_str()
        );

        self.closed_trades.push(trade.clone());
        Some(trade)
    }

    /// Get all open positions
    pub fn open_positions(&self) -> &[Position] {
        &self.positions
    }

    /// Get all closed trades today
    pub fn closed_trades(&self) -> &[ClosedTrade] {
        &self.closed_trades
    }

    /// Total unrealized P&L
    pub fn unrealized_pnl(&self) -> Decimal {
        self.positions.iter().map(|p| p.pnl).sum()
    }

    /// Total realized P&L
    pub fn realized_pnl(&self) -> Decimal {
        self.closed_trades.iter().map(|t| t.pnl).sum()
    }

    /// Close all positions (force exit / kill switch)
    pub fn force_close_all(&mut self) -> Vec<usize> {
        (0..self.positions.len()).collect()
    }
}

impl ClosedTrade {
    pub fn reason_str(&self) -> &str {
        match &self.reason {
            CloseReason::Target => "TARGET",
            CloseReason::StopLoss => "STOPLOSS",
            CloseReason::TrailingStop => "TRAILING",
            CloseReason::SignalFlip => "SIGNAL_FLIP",
            CloseReason::TimeExit => "TIME_EXIT",
            CloseReason::KillSwitch => "KILL_SWITCH",
            CloseReason::Manual => "MANUAL",
        }
    }
}
