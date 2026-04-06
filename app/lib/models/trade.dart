class Trade {
  final String type; // 'buy' or 'sell'
  final String symbol;
  final int qty;
  final double price;
  final double total;
  final double? pnl;
  final double? pnlPct;
  final DateTime timestamp;

  const Trade({
    required this.type,
    required this.symbol,
    required this.qty,
    required this.price,
    required this.total,
    this.pnl,
    this.pnlPct,
    required this.timestamp,
  });

  factory Trade.fromJson(Map<String, dynamic> json) {
    final qty = _toInt(json['qty'] ?? json['quantity'] ?? 0);
    final price = _toDouble(json['price'] ?? json['trade_price'] ?? 0);
    final total = _toDouble(json['total'] ?? json['amount'] ?? (qty * price));

    return Trade(
      type: json['type']?.toString().toLowerCase() ?? 'buy',
      symbol: json['symbol']?.toString() ?? '',
      qty: qty,
      price: price,
      total: total,
      pnl: json['pnl'] != null ? _toDouble(json['pnl']) : null,
      pnlPct: json['pnl_pct'] != null ? _toDouble(json['pnl_pct']) : null,
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'type': type,
    'symbol': symbol,
    'qty': qty,
    'price': price,
    'total': total,
    'pnl': pnl,
    'pnl_pct': pnlPct,
    'timestamp': timestamp.toIso8601String(),
  };

  bool get isBuy => type.toLowerCase() == 'buy';
  bool get isProfitable => pnl != null && pnl! > 0;

  static double _toDouble(dynamic value) {
    if (value == null) return 0.0;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    return double.tryParse(value.toString()) ?? 0.0;
  }

  static int _toInt(dynamic value) {
    if (value == null) return 0;
    if (value is int) return value;
    if (value is double) return value.toInt();
    return int.tryParse(value.toString()) ?? 0;
  }
}
