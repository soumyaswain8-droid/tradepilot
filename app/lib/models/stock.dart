class Stock {
  final String symbol;
  final String name;
  final String direction;
  final String trend;
  final String volatility;
  final String macd;
  final double price;
  final double change;
  final double score;
  final double rsi;
  final double stopLoss;
  final double target;
  final double riskReward;

  const Stock({
    required this.symbol,
    required this.name,
    required this.direction,
    required this.trend,
    required this.volatility,
    required this.macd,
    required this.price,
    required this.change,
    required this.score,
    required this.rsi,
    required this.stopLoss,
    required this.target,
    required this.riskReward,
  });

  factory Stock.fromJson(Map<String, dynamic> json) {
    return Stock(
      symbol: json['symbol']?.toString() ?? '',
      name: json['name']?.toString() ?? json['symbol']?.toString() ?? '',
      direction: json['direction']?.toString() ?? json['signal']?.toString() ?? 'HOLD',
      trend: json['trend']?.toString() ?? '',
      volatility: json['volatility']?.toString() ?? '',
      macd: json['macd']?.toString() ?? '',
      price: _toDouble(json['price'] ?? json['ltp'] ?? json['last_price'] ?? 0),
      change: _toDouble(json['change'] ?? json['change_pct'] ?? json['day_change_pct'] ?? 0),
      score: _toDouble(json['score'] ?? json['profit_probability'] ?? json['ai_score'] ?? 0),
      rsi: _toDouble(json['rsi'] ?? 50),
      stopLoss: _toDouble(json['stop_loss'] ?? json['stopLoss'] ?? 0),
      target: _toDouble(json['target'] ?? json['target_price'] ?? 0),
      riskReward: _toDouble(json['risk_reward'] ?? json['riskReward'] ?? 0),
    );
  }

  Map<String, dynamic> toJson() => {
    'symbol': symbol,
    'name': name,
    'direction': direction,
    'trend': trend,
    'volatility': volatility,
    'macd': macd,
    'price': price,
    'change': change,
    'score': score,
    'rsi': rsi,
    'stop_loss': stopLoss,
    'target': target,
    'risk_reward': riskReward,
  };

  static double _toDouble(dynamic value) {
    if (value == null) return 0.0;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    return double.tryParse(value.toString()) ?? 0.0;
  }

  Stock copyWith({
    String? symbol,
    String? name,
    String? direction,
    String? trend,
    String? volatility,
    String? macd,
    double? price,
    double? change,
    double? score,
    double? rsi,
    double? stopLoss,
    double? target,
    double? riskReward,
  }) {
    return Stock(
      symbol: symbol ?? this.symbol,
      name: name ?? this.name,
      direction: direction ?? this.direction,
      trend: trend ?? this.trend,
      volatility: volatility ?? this.volatility,
      macd: macd ?? this.macd,
      price: price ?? this.price,
      change: change ?? this.change,
      score: score ?? this.score,
      rsi: rsi ?? this.rsi,
      stopLoss: stopLoss ?? this.stopLoss,
      target: target ?? this.target,
      riskReward: riskReward ?? this.riskReward,
    );
  }
}
