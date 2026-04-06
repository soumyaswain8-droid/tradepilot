class AppUser {
  final String id;
  final String phone;
  final String name;
  final double cash;
  final double initialCash;
  final DateTime createdAt;

  const AppUser({
    required this.id,
    required this.phone,
    required this.name,
    required this.cash,
    required this.initialCash,
    required this.createdAt,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: json['id']?.toString() ?? json['phone']?.toString() ?? '',
      phone: json['phone']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      cash: _toDouble(json['cash'] ?? json['available_cash'] ?? 1000000),
      initialCash: _toDouble(json['initial_cash'] ?? json['initialCash'] ?? 1000000),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  factory AppUser.fromPrefs({
    required String phone,
    required String name,
    required double cash,
    required double initialCash,
    required DateTime createdAt,
  }) {
    return AppUser(
      id: phone,
      phone: phone,
      name: name,
      cash: cash,
      initialCash: initialCash,
      createdAt: createdAt,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'phone': phone,
    'name': name,
    'cash': cash,
    'initial_cash': initialCash,
    'created_at': createdAt.toIso8601String(),
  };

  String get initials {
    if (name.isEmpty) return phone.isNotEmpty ? phone.substring(phone.length - 2) : 'TP';
    final parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    return name.substring(0, name.length.clamp(1, 2)).toUpperCase();
  }

  double get pnlPercent => initialCash > 0 ? ((cash - initialCash) / initialCash) * 100 : 0;

  static double _toDouble(dynamic value) {
    if (value == null) return 0.0;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    return double.tryParse(value.toString()) ?? 0.0;
  }
}
