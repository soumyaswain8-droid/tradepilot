import 'package:shared_preferences/shared_preferences.dart';
import '../models/user.dart';

class AuthService {
  static const _keyPhone = 'tp_phone';
  static const _keyName = 'tp_name';
  static const _keyLoggedIn = 'tp_logged_in';
  static const _keyCash = 'tp_cash';
  static const _keyInitialCash = 'tp_initial_cash';
  static const _keyCreatedAt = 'tp_created_at';
  static const String _demoOtp = '1234';
  static const double _startingCash = 1000000.0; // Rs 10 Lakh

  // Simulate sending OTP — always returns true in demo mode
  static Future<bool> loginWithPhone(String phone) async {
    // Validate phone number
    if (phone.length < 10) return false;
    // In demo mode, always succeed
    await Future.delayed(const Duration(milliseconds: 800)); // simulate network
    return true;
  }

  // Verify OTP — accepts "1234" always in demo mode
  static Future<bool> verifyOtp(String phone, String otp) async {
    await Future.delayed(const Duration(milliseconds: 600)); // simulate network
    return otp == _demoOtp || otp.length == 4; // demo: any 4-digit OTP works
  }

  // Save user and log them in
  static Future<AppUser> saveUser({
    required String phone,
    required String name,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();

    await prefs.setString(_keyPhone, phone);
    await prefs.setString(_keyName, name.isEmpty ? 'Trader' : name);
    await prefs.setBool(_keyLoggedIn, true);
    await prefs.setDouble(_keyCash, _startingCash);
    await prefs.setDouble(_keyInitialCash, _startingCash);
    await prefs.setString(_keyCreatedAt, now.toIso8601String());

    return AppUser.fromPrefs(
      phone: phone,
      name: name.isEmpty ? 'Trader' : name,
      cash: _startingCash,
      initialCash: _startingCash,
      createdAt: now,
    );
  }

  static Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyLoggedIn) ?? false;
  }

  static Future<AppUser?> getCurrentUser() async {
    final prefs = await SharedPreferences.getInstance();
    final loggedIn = prefs.getBool(_keyLoggedIn) ?? false;
    if (!loggedIn) return null;

    final phone = prefs.getString(_keyPhone) ?? '';
    final name = prefs.getString(_keyName) ?? 'Trader';
    final cash = prefs.getDouble(_keyCash) ?? _startingCash;
    final initialCash = prefs.getDouble(_keyInitialCash) ?? _startingCash;
    final createdAtStr = prefs.getString(_keyCreatedAt);
    final createdAt = createdAtStr != null
        ? DateTime.tryParse(createdAtStr) ?? DateTime.now()
        : DateTime.now();

    return AppUser.fromPrefs(
      phone: phone,
      name: name,
      cash: cash,
      initialCash: initialCash,
      createdAt: createdAt,
    );
  }

  static Future<void> updateCash(double newCash) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyCash, newCash);
  }

  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyPhone);
    await prefs.remove(_keyName);
    await prefs.remove(_keyLoggedIn);
    await prefs.remove(_keyCash);
    await prefs.remove(_keyInitialCash);
    await prefs.remove(_keyCreatedAt);
  }

  static Future<void> resetAccount() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyCash, _startingCash);
    await prefs.setDouble(_keyInitialCash, _startingCash);
  }
}
