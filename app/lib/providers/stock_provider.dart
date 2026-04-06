import 'package:flutter/foundation.dart';
import '../models/stock.dart';
import '../models/trade.dart';
import '../models/position.dart';
import '../services/api_service.dart';

class StockProvider extends ChangeNotifier {
  List<Stock> _stocks = [];
  List<Stock> _gainers = [];
  List<Stock> _losers = [];
  List<Map<String, dynamic>> _categories = [];
  List<Position> _positions = [];
  List<Trade> _trades = [];
  Map<String, dynamic> _portfolio = {};
  String _selectedCategory = 'nifty50';
  bool _isLoading = false;
  bool _isPortfolioLoading = false;
  String? _error;

  List<Stock> get stocks => _stocks;
  List<Stock> get gainers => _gainers;
  List<Stock> get losers => _losers;
  List<Map<String, dynamic>> get categories => _categories;
  List<Position> get positions => _positions;
  List<Trade> get trades => _trades;
  Map<String, dynamic> get portfolio => _portfolio;
  String get selectedCategory => _selectedCategory;
  bool get isLoading => _isLoading;
  bool get isPortfolioLoading => _isPortfolioLoading;
  String? get error => _error;

  double get portfolioValue => _toDouble(_portfolio['portfolio_value'] ?? _portfolio['total_value'] ?? 0);
  double get availableCash => _toDouble(_portfolio['cash'] ?? _portfolio['available_cash'] ?? 1000000);
  double get totalPnl => _toDouble(_portfolio['total_pnl'] ?? 0);
  double get totalPnlPct => _toDouble(_portfolio['total_pnl_pct'] ?? 0);
  int get totalTrades => _toInt(_portfolio['total_trades'] ?? _trades.length);
  int get winTrades => _toInt(_portfolio['win_trades'] ?? 0);
  int get lossTrades => _toInt(_portfolio['loss_trades'] ?? 0);

  Future<void> loadCategories() async {
    _categories = await ApiService.getCategories();
    notifyListeners();
  }

  Future<void> loadStocks({String? category}) async {
    final cat = category ?? _selectedCategory;
    _selectedCategory = cat;
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _stocks = await ApiService.getScores(cat);
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> selectCategory(String category) async {
    if (_selectedCategory == category) return;
    _selectedCategory = category;
    await loadStocks(category: category);
  }

  Future<void> loadGainersLosers() async {
    _isLoading = true;
    notifyListeners();

    try {
      final result = await ApiService.getGainersLosers();
      _gainers = result['gainers'] ?? [];
      _losers = result['losers'] ?? [];
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadPortfolio() async {
    _isPortfolioLoading = true;
    notifyListeners();

    try {
      final result = await Future.wait([
        ApiService.getPortfolio(),
        ApiService.getPositions(),
        ApiService.getTradeHistory(),
      ]);
      _portfolio = result[0] as Map<String, dynamic>;
      _positions = result[1] as List<Position>;
      _trades = result[2] as List<Trade>;
    } catch (e) {
      _error = e.toString();
    } finally {
      _isPortfolioLoading = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> executeBuy(String symbol, int qty) async {
    final result = await ApiService.executeBuy(symbol, qty);
    if (result['success'] == true || result['status'] == 'success') {
      await loadPortfolio();
    }
    return result;
  }

  Future<Map<String, dynamic>> executeSell(String symbol, int qty) async {
    final result = await ApiService.executeSell(symbol, qty);
    if (result['success'] == true || result['status'] == 'success') {
      await loadPortfolio();
    }
    return result;
  }

  Future<void> resetPortfolio() async {
    await ApiService.resetPortfolio();
    await loadPortfolio();
  }

  Stock? findStock(String symbol) {
    try {
      return _stocks.firstWhere(
        (s) => s.symbol.toUpperCase() == symbol.toUpperCase(),
      );
    } catch (_) {
      return null;
    }
  }

  List<Stock> searchStocks(String query) {
    if (query.isEmpty) return _stocks;
    final q = query.toUpperCase();
    return _stocks.where((s) =>
      s.symbol.toUpperCase().contains(q) ||
      s.name.toUpperCase().contains(q)
    ).toList();
  }

  static double _toDouble(dynamic v) {
    if (v == null) return 0.0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse(v.toString()) ?? 0.0;
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
