import 'package:flutter/foundation.dart';
import '../models/user.dart';
import '../services/auth_service.dart';

class AuthProvider extends ChangeNotifier {
  AppUser? _user;
  bool _isLoading = false;
  String? _error;
  bool _otpSent = false;

  AppUser? get user => _user;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _user != null;
  bool get otpSent => _otpSent;

  Future<void> checkAuth() async {
    _isLoading = true;
    notifyListeners();

    try {
      final loggedIn = await AuthService.isLoggedIn();
      if (loggedIn) {
        _user = await AuthService.getCurrentUser();
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> sendOtp(String phone) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await AuthService.loginWithPhone(phone);
      _otpSent = result;
      return result;
    } catch (e) {
      _error = e.toString();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> login({
    required String phone,
    required String otp,
    required String name,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final verified = await AuthService.verifyOtp(phone, otp);
      if (!verified) {
        _error = 'Invalid OTP. Use 1234 for demo.';
        return false;
      }

      _user = await AuthService.saveUser(phone: phone, name: name);
      return true;
    } catch (e) {
      _error = e.toString();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    await AuthService.logout();
    _user = null;
    _otpSent = false;
    _error = null;
    notifyListeners();
  }

  Future<void> resetAccount() async {
    await AuthService.resetAccount();
    _user = await AuthService.getCurrentUser();
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }

  void resetOtpState() {
    _otpSent = false;
    notifyListeners();
  }
}
