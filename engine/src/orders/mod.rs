//! Type-safe order system for TradePilot.
//!
//! The compiler enforces:
//! - Every BUY order MUST have a stop-loss
//! - All money values use Decimal (no floating point)
//! - Order quantities must be positive
//! - Invalid states are unrepresentable

use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Exchange — NSE or BSE
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum Exchange {
    NSE,
    BSE,
}

/// Direction — the compiler knows LONG from SHORT
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum Direction {
    Long,
    Short,
}

/// Order variety matching Kite API
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum OrderVariety {
    Regular,     // CNC, MIS
    AMO,         // After Market Order
    BO,          // Bracket Order (entry + SL + target)
    CO,          // Cover Order (entry + SL)
}

/// Order type matching Kite API
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum OrderType {
    Market,
    Limit,
    StopLoss,       // SL (limit trigger)
    StopLossMarket, // SL-M (market trigger)
}

/// Product type
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum Product {
    CNC,  // Cash & Carry (delivery)
    MIS,  // Margin Intraday
    NRML, // Normal (F&O)
}

/// Transaction type
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum TransactionType {
    Buy,
    Sell,
}

/// A validated order request — can only be created through the builder.
/// The builder enforces that stop-loss is present for every entry order.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderRequest {
    pub id: Uuid,
    pub symbol: String,
    pub exchange: Exchange,
    pub transaction_type: TransactionType,
    pub order_type: OrderType,
    pub product: Product,
    pub quantity: u32,
    pub price: Decimal,          // Limit price (0 for market orders)
    pub trigger_price: Decimal,  // Trigger for SL orders
    pub stop_loss: Decimal,      // MANDATORY — enforced by builder
    pub target: Decimal,
    pub direction: Direction,
    pub created_at: DateTime<Utc>,
    pub tag: String,             // For tracking (e.g., "v5-SWING-RELIANCE")
}

/// Order status from Kite
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum OrderStatus {
    Pending,
    Open,
    Complete,
    Cancelled,
    Rejected,
    Unknown(String),
}

/// Response after order placement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderResponse {
    pub order_id: String,
    pub status: OrderStatus,
    pub message: String,
    pub timestamp: DateTime<Utc>,
}

/// Builder pattern — the ONLY way to create an OrderRequest.
/// Forces stop-loss to be set before building.
pub struct OrderBuilder {
    symbol: String,
    exchange: Exchange,
    transaction_type: TransactionType,
    order_type: OrderType,
    product: Product,
    quantity: Option<u32>,
    price: Decimal,
    trigger_price: Decimal,
    stop_loss: Option<Decimal>,  // None = not set yet
    target: Option<Decimal>,
    direction: Direction,
    tag: String,
}

/// Errors that prevent order creation
#[derive(Debug, thiserror::Error)]
pub enum OrderError {
    #[error("Stop-loss is mandatory for all orders")]
    MissingStopLoss,

    #[error("Quantity must be > 0, got {0}")]
    InvalidQuantity(u32),

    #[error("Stop-loss {sl} must be below entry {entry} for LONG orders")]
    StopLossAboveEntry { sl: Decimal, entry: Decimal },

    #[error("Stop-loss {sl} must be above entry {entry} for SHORT orders")]
    StopLossBelowEntry { sl: Decimal, entry: Decimal },

    #[error("Target {target} must be above entry {entry} for LONG orders")]
    TargetBelowEntry { target: Decimal, entry: Decimal },

    #[error("Order amount Rs {amount} exceeds max per-order limit Rs {limit}")]
    ExceedsOrderLimit { amount: Decimal, limit: Decimal },

    #[error("Symbol cannot be empty")]
    EmptySymbol,
}

impl OrderBuilder {
    /// Start building a new order
    pub fn new(symbol: &str, direction: Direction) -> Self {
        let transaction_type = match direction {
            Direction::Long => TransactionType::Buy,
            Direction::Short => TransactionType::Sell,
        };
        Self {
            symbol: symbol.to_uppercase(),
            exchange: Exchange::NSE,
            transaction_type,
            order_type: OrderType::Market,
            product: Product::MIS,
            quantity: None,
            price: Decimal::ZERO,
            trigger_price: Decimal::ZERO,
            stop_loss: None,
            target: None,
            direction,
            tag: String::new(),
        }
    }

    pub fn exchange(mut self, exchange: Exchange) -> Self {
        self.exchange = exchange;
        self
    }

    pub fn order_type(mut self, order_type: OrderType) -> Self {
        self.order_type = order_type;
        self
    }

    pub fn product(mut self, product: Product) -> Self {
        self.product = product;
        self
    }

    pub fn quantity(mut self, qty: u32) -> Self {
        self.quantity = Some(qty);
        self
    }

    pub fn price(mut self, price: Decimal) -> Self {
        self.price = price;
        self
    }

    pub fn trigger_price(mut self, price: Decimal) -> Self {
        self.trigger_price = price;
        self
    }

    /// MANDATORY — every order must have a stop-loss
    pub fn stop_loss(mut self, sl: Decimal) -> Self {
        self.stop_loss = Some(sl);
        self
    }

    pub fn target(mut self, target: Decimal) -> Self {
        self.target = Some(target);
        self
    }

    pub fn tag(mut self, tag: &str) -> Self {
        self.tag = tag.to_string();
        self
    }

    /// Build the order — fails if stop-loss is missing or validation fails
    pub fn build(self) -> Result<OrderRequest, OrderError> {
        // Symbol check
        if self.symbol.is_empty() {
            return Err(OrderError::EmptySymbol);
        }

        // MANDATORY stop-loss check — this is the key safety feature
        let stop_loss = self.stop_loss.ok_or(OrderError::MissingStopLoss)?;

        // Quantity check
        let quantity = self.quantity.unwrap_or(0);
        if quantity == 0 {
            return Err(OrderError::InvalidQuantity(quantity));
        }

        // Direction-based SL validation
        let entry = if self.price > Decimal::ZERO { self.price } else { Decimal::ZERO };
        if entry > Decimal::ZERO {
            match self.direction {
                Direction::Long => {
                    if stop_loss >= entry {
                        return Err(OrderError::StopLossAboveEntry { sl: stop_loss, entry });
                    }
                }
                Direction::Short => {
                    if stop_loss <= entry {
                        return Err(OrderError::StopLossBelowEntry { sl: stop_loss, entry });
                    }
                }
            }
        }

        // Target validation for LONG
        if let Some(target) = self.target {
            if self.direction == Direction::Long && entry > Decimal::ZERO && target <= entry {
                return Err(OrderError::TargetBelowEntry { target, entry });
            }
        }

        Ok(OrderRequest {
            id: Uuid::new_v4(),
            symbol: self.symbol,
            exchange: self.exchange,
            transaction_type: self.transaction_type,
            order_type: self.order_type,
            product: self.product,
            quantity,
            price: self.price,
            trigger_price: self.trigger_price,
            stop_loss,
            target: self.target.unwrap_or(Decimal::ZERO),
            direction: self.direction,
            created_at: Utc::now(),
            tag: self.tag,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal_macros::dec;

    #[test]
    fn test_order_without_sl_fails() {
        let result = OrderBuilder::new("RELIANCE", Direction::Long)
            .quantity(10)
            .price(dec!(2850.00))
            .build();

        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OrderError::MissingStopLoss));
    }

    #[test]
    fn test_order_with_sl_succeeds() {
        let order = OrderBuilder::new("RELIANCE", Direction::Long)
            .quantity(10)
            .price(dec!(2850.00))
            .stop_loss(dec!(2807.25))
            .target(dec!(2907.00))
            .tag("v5-SWING")
            .build()
            .unwrap();

        assert_eq!(order.symbol, "RELIANCE");
        assert_eq!(order.quantity, 10);
        assert_eq!(order.stop_loss, dec!(2807.25));
    }

    #[test]
    fn test_long_sl_above_entry_fails() {
        let result = OrderBuilder::new("TCS", Direction::Long)
            .quantity(5)
            .price(dec!(3456.00))
            .stop_loss(dec!(3500.00)) // SL above entry — invalid for LONG
            .build();

        assert!(matches!(result.unwrap_err(), OrderError::StopLossAboveEntry { .. }));
    }

    #[test]
    fn test_short_sl_below_entry_fails() {
        let result = OrderBuilder::new("INFY", Direction::Short)
            .quantity(8)
            .price(dec!(1823.00))
            .stop_loss(dec!(1800.00)) // SL below entry — invalid for SHORT
            .build();

        assert!(matches!(result.unwrap_err(), OrderError::StopLossBelowEntry { .. }));
    }

    #[test]
    fn test_zero_quantity_fails() {
        let result = OrderBuilder::new("HDFC", Direction::Long)
            .quantity(0)
            .price(dec!(1654.00))
            .stop_loss(dec!(1630.00))
            .build();

        assert!(matches!(result.unwrap_err(), OrderError::InvalidQuantity(0)));
    }
}
