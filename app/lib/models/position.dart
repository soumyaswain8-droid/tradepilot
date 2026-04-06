class Position {
  final String symbol;
  final int qty;
  final double avgPrice;
  final double currentPrice;
  final double pnl;
  final double pnlPct;

  const Position({
    required this.symbol,
    required this.qty,
    required this.avgPrice,
    required this.currentPrice,
    required this.pnl,
    required this.pnlPct,
  });

  factory Position.fromJson(Map<String, dynamic> json) {
    final qty = _toInt(json['qty'] ?? json['quantity'] ?? 0);
    final avgPrice = _toDouble(json['avg_price'] ?? json['avgPrice'] ?? json['average_price'] ?? 0);
    final currentPrice = _toDouble(json['current_price'] ?? json['currentPrice'] ?? json['ltp'] ?? avgPrice);
    final invested = qty * avgPrice;
    final current = qty * currentPrice;
    final pnl = _toDouble(json['pnl'] ?? json['unrealized_pnl'] ?? (current - invested));
    final pnlPct = _toDouble(json['pnl_pct'] ?? json['pnlPct'] ?? (invested > 0 ? ((current - invested) / invested) * 100 : 0));

    return Position(
      symbol: json['symbol']?.toString() ?? '',
      qty: qty,
      avgPrice: avgPrice,
      currentPrice: currentPrice,
      pnl: pnl,
      pnlPct: pnlPct,
    );
  }

  Map<String, dynamic> toJson() => {
    'symbol': symbol,
    'qty': qty,
    'avg_price': avgPrice,
    'current_price': currentPrice,
    'pnl': pnl,
    'pnl_pct': pnlPct,
  };

  double get invested => qty * avgPrice;
  double get currentValue => qty * currentPrice;
  bool get isProfitable => pnl >= 0;

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
