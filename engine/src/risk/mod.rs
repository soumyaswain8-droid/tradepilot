//! Risk management — compile-time enforced safety for live trading.
//!
//! Hard limits that CANNOT be bypassed:
//! - Daily loss limit (kill switch)
//! - Per-order size limit
//! - Max positions per symbol
//! - Max total positions
//! - Max capital deployment percentage

use chrono::{DateTime, NaiveTime, Utc};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::orders::{Direction, OrderRequest};

/// Risk configuration — loaded from config, immutable during trading
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskConfig {
    /// Maximum loss per day before ALL trading stops (hard kill switch)
    pub max_daily_loss: Decimal,

    /// Maximum single order value (prevents fat-finger errors)
    pub max_order_value: Decimal,

    /// Maximum number of concurrent positions
    pub max_total_positions: u32,

    /// Maximum positions per single stock
    pub max_positions_per_symbol: u32,

    /// Maximum percentage of capital deployed at once
    pub max_deployment_pct: Decimal,

    /// Total trading capital
    pub total_capital: Decimal,

    /// Force-close all intraday positions at this time
    pub force_exit_time: NaiveTime,

    /// VIX threshold — reduce position sizes above this
    pub high_vix_threshold: Decimal,

    /// VIX multiplier when above threshold (e.g., 0.5 = half size)
    pub high_vix_size_multiplier: Decimal,
}

impl Default for RiskConfig {
    fn default() -> Self {
        Self {
            max_daily_loss: dec!(-20000),           // Rs 20K hard stop
            max_order_value: dec!(100000),           // Rs 1L max per order
            max_total_positions: 30,
            max_positions_per_symbol: 3,
            max_deployment_pct: dec!(0.80),          // 80% max deployed
            total_capital: dec!(1000000),             // Rs 10L
            force_exit_time: NaiveTime::from_hms_opt(15, 15, 0).unwrap(),
            high_vix_threshold: dec!(20),
            high_vix_size_multiplier: dec!(0.50),
        }
    }
}

/// Live risk state — tracks P&L and positions in real-time
#[derive(Debug)]
pub struct RiskManager {
    config: RiskConfig,
    daily_pnl: Decimal,
    realized_pnl: Decimal,
    unrealized_pnl: Decimal,
    positions_count: u32,
    positions_by_symbol: HashMap<String, u32>,
    total_deployed: Decimal,
    killed: bool,              // Once true, NO more trading
    kill_reason: Option<String>,
    current_vix: Decimal,
}

/// Reasons an order can be rejected
#[derive(Debug, thiserror::Error)]
pub enum RiskRejection {
    #[error("KILL SWITCH ACTIVE: {reason}. No trading allowed.")]
    KillSwitchActive { reason: String },

    #[error("Daily loss limit breached: Rs {pnl} (limit: Rs {limit})")]
    DailyLossLimitBreached { pnl: Decimal, limit: Decimal },

    #[error("Order value Rs {value} exceeds max Rs {limit}")]
    OrderTooLarge { value: Decimal, limit: Decimal },

    #[error("Max positions reached: {count}/{limit}")]
    MaxPositionsReached { count: u32, limit: u32 },

    #[error("Max positions for {symbol}: {count}/{limit}")]
    MaxPositionsForSymbol { symbol: String, count: u32, limit: u32 },

    #[error("Deployment {pct}% would exceed max {limit}%")]
    MaxDeploymentExceeded { pct: Decimal, limit: Decimal },

    #[error("Trading hours ended — force exit time passed")]
    AfterForceExitTime,
}

/// Result of a risk check
pub type RiskResult = Result<(), RiskRejection>;

impl RiskManager {
    pub fn new(config: RiskConfig) -> Self {
        Self {
            config,
            daily_pnl: Decimal::ZERO,
            realized_pnl: Decimal::ZERO,
            unrealized_pnl: Decimal::ZERO,
            positions_count: 0,
            positions_by_symbol: HashMap::new(),
            total_deployed: Decimal::ZERO,
            killed: false,
            kill_reason: None,
            current_vix: dec!(15),
        }
    }

    /// Check if an order passes ALL risk gates. Returns Ok(()) or specific rejection.
    pub fn check_order(&self, order: &OrderRequest) -> RiskResult {
        // Gate 1: Kill switch
        if self.killed {
            return Err(RiskRejection::KillSwitchActive {
                reason: self.kill_reason.clone().unwrap_or_default(),
            });
        }

        // Gate 2: Daily loss limit
        if self.daily_pnl <= self.config.max_daily_loss {
            return Err(RiskRejection::DailyLossLimitBreached {
                pnl: self.daily_pnl,
                limit: self.config.max_daily_loss,
            });
        }

        // Gate 3: Order size limit
        let order_value = Decimal::from(order.quantity) * order.price;
        if order_value > self.config.max_order_value {
            return Err(RiskRejection::OrderTooLarge {
                value: order_value,
                limit: self.config.max_order_value,
            });
        }

        // Gate 4: Total positions
        if self.positions_count >= self.config.max_total_positions {
            return Err(RiskRejection::MaxPositionsReached {
                count: self.positions_count,
                limit: self.config.max_total_positions,
            });
        }

        // Gate 5: Per-symbol positions
        let sym_count = self.positions_by_symbol.get(&order.symbol).copied().unwrap_or(0);
        if sym_count >= self.config.max_positions_per_symbol {
            return Err(RiskRejection::MaxPositionsForSymbol {
                symbol: order.symbol.clone(),
                count: sym_count,
                limit: self.config.max_positions_per_symbol,
            });
        }

        // Gate 6: Max capital deployment
        let new_deployed = self.total_deployed + order_value;
        let deploy_pct = new_deployed / self.config.total_capital * dec!(100);
        let max_pct = self.config.max_deployment_pct * dec!(100);
        if deploy_pct > max_pct {
            return Err(RiskRejection::MaxDeploymentExceeded {
                pct: deploy_pct,
                limit: max_pct,
            });
        }

        // Gate 7: Time check
        let now = Utc::now().time();
        if now >= self.config.force_exit_time {
            return Err(RiskRejection::AfterForceExitTime);
        }

        Ok(())
    }

    /// Record a new position being opened
    pub fn record_position_opened(&mut self, symbol: &str, value: Decimal) {
        self.positions_count += 1;
        *self.positions_by_symbol.entry(symbol.to_string()).or_insert(0) += 1;
        self.total_deployed += value;
    }

    /// Record a position being closed
    pub fn record_position_closed(&mut self, symbol: &str, value: Decimal, pnl: Decimal) {
        self.positions_count = self.positions_count.saturating_sub(1);
        if let Some(count) = self.positions_by_symbol.get_mut(symbol) {
            *count = count.saturating_sub(1);
            if *count == 0 {
                self.positions_by_symbol.remove(symbol);
            }
        }
        self.total_deployed = (self.total_deployed - value).max(Decimal::ZERO);
        self.realized_pnl += pnl;
        self.daily_pnl = self.realized_pnl + self.unrealized_pnl;

        // Auto kill-switch check
        if self.daily_pnl <= self.config.max_daily_loss {
            self.activate_kill_switch(format!(
                "Daily loss Rs {} exceeded limit Rs {}",
                self.daily_pnl, self.config.max_daily_loss
            ));
        }
    }

    /// Update unrealized P&L from live prices
    pub fn update_unrealized_pnl(&mut self, unrealized: Decimal) {
        self.unrealized_pnl = unrealized;
        self.daily_pnl = self.realized_pnl + self.unrealized_pnl;

        // Check kill switch on unrealized too
        if self.daily_pnl <= self.config.max_daily_loss && !self.killed {
            self.activate_kill_switch(format!(
                "Unrealized daily loss Rs {} hit limit Rs {}",
                self.daily_pnl, self.config.max_daily_loss
            ));
        }
    }

    /// Manually activate kill switch (emergency stop)
    pub fn activate_kill_switch(&mut self, reason: String) {
        self.killed = true;
        self.kill_reason = Some(reason.clone());
        tracing::error!("KILL SWITCH ACTIVATED: {}", reason);
    }

    /// Update VIX for position sizing
    pub fn set_vix(&mut self, vix: Decimal) {
        self.current_vix = vix;
    }

    /// Get position size multiplier based on VIX
    pub fn vix_size_multiplier(&self) -> Decimal {
        if self.current_vix > self.config.high_vix_threshold {
            self.config.high_vix_size_multiplier
        } else {
            dec!(1.0)
        }
    }

    /// Is the kill switch active?
    pub fn is_killed(&self) -> bool {
        self.killed
    }

    /// Get current daily P&L
    pub fn daily_pnl(&self) -> Decimal {
        self.daily_pnl
    }

    /// Get risk state summary
    pub fn status(&self) -> RiskStatus {
        RiskStatus {
            daily_pnl: self.daily_pnl,
            realized_pnl: self.realized_pnl,
            unrealized_pnl: self.unrealized_pnl,
            positions_count: self.positions_count,
            total_deployed: self.total_deployed,
            killed: self.killed,
            kill_reason: self.kill_reason.clone(),
            vix: self.current_vix,
            deployment_pct: if self.config.total_capital > Decimal::ZERO {
                (self.total_deployed / self.config.total_capital * dec!(100)).round_dp(1)
            } else {
                Decimal::ZERO
            },
        }
    }

    /// Reset daily counters (call at start of new trading day)
    pub fn reset_daily(&mut self) {
        self.daily_pnl = Decimal::ZERO;
        self.realized_pnl = Decimal::ZERO;
        self.unrealized_pnl = Decimal::ZERO;
        self.killed = false;
        self.kill_reason = None;
    }
}

/// Serializable risk status for API/display
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskStatus {
    pub daily_pnl: Decimal,
    pub realized_pnl: Decimal,
    pub unrealized_pnl: Decimal,
    pub positions_count: u32,
    pub total_deployed: Decimal,
    pub killed: bool,
    pub kill_reason: Option<String>,
    pub vix: Decimal,
    pub deployment_pct: Decimal,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::orders::{OrderBuilder, Direction};

    #[test]
    fn test_kill_switch_blocks_all_orders() {
        let mut rm = RiskManager::new(RiskConfig::default());
        rm.activate_kill_switch("Manual emergency stop".into());

        let order = OrderBuilder::new("RELIANCE", Direction::Long)
            .quantity(10)
            .price(dec!(2850))
            .stop_loss(dec!(2807))
            .build()
            .unwrap();

        let result = rm.check_order(&order);
        assert!(matches!(result, Err(RiskRejection::KillSwitchActive { .. })));
    }

    #[test]
    fn test_daily_loss_limit_triggers_kill() {
        let config = RiskConfig {
            max_daily_loss: dec!(-5000),
            ..Default::default()
        };
        let mut rm = RiskManager::new(config);

        // Simulate a big loss
        rm.record_position_closed("RELIANCE", dec!(28500), dec!(-6000));

        assert!(rm.is_killed());
    }

    #[test]
    fn test_order_too_large_rejected() {
        let config = RiskConfig {
            max_order_value: dec!(50000),
            ..Default::default()
        };
        let rm = RiskManager::new(config);

        let order = OrderBuilder::new("RELIANCE", Direction::Long)
            .quantity(100)
            .price(dec!(2850)) // 100 * 2850 = Rs 2,85,000 > 50,000 limit
            .stop_loss(dec!(2807))
            .build()
            .unwrap();

        let result = rm.check_order(&order);
        assert!(matches!(result, Err(RiskRejection::OrderTooLarge { .. })));
    }

    #[test]
    fn test_valid_order_passes_all_gates() {
        let config = RiskConfig {
            force_exit_time: NaiveTime::from_hms_opt(23, 59, 0).unwrap(), // Override for test
            ..Default::default()
        };
        let rm = RiskManager::new(config);

        let order = OrderBuilder::new("TCS", Direction::Long)
            .quantity(5)
            .price(dec!(3456))
            .stop_loss(dec!(3400))
            .target(dec!(3525))
            .build()
            .unwrap();

        assert!(rm.check_order(&order).is_ok());
    }
}
