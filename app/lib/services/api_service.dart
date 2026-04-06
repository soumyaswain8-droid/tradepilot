import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/stock.dart';
import '../models/trade.dart';
import '../models/position.dart';

class ApiService {
  static String _baseUrl = 'http://localhost:5050';

  static void setBaseUrl(String url) {
    _baseUrl = url;
  }

  static String get baseUrl => _baseUrl;

  static final _client = http.Client();

  static Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  // GET /scores?category=nifty50
  static Future<List<Stock>> getScores(String category) async {
    try {
      final uri = Uri.parse('$_baseUrl/api/scores').replace(
        queryParameters: {'category': category},
      );
      final response = await _client
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        List<dynamic> items = [];

        if (data is List) {
          items = data;
        } else if (data is Map && data['stocks'] != null) {
          items = data['stocks'] as List;
        } else if (data is Map && data['data'] != null) {
          items = data['data'] as List;
        } else if (data is Map && data['results'] != null) {
          items = data['results'] as List;
        }

        if (items.isNotEmpty) {
          return items
              .map((e) => Stock.fromJson(e as Map<String, dynamic>))
              .toList();
        }
      }
      return _mockStocks(category);
    } catch (_) {
      return _mockStocks(category);
    }
  }

  // GET /gainers-losers
  static Future<Map<String, List<Stock>>> getGainersLosers() async {
    try {
      final uri = Uri.parse('$_baseUrl/api/gainers-losers');
      final response = await _client
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'gainers': (data['gainers'] as List? ?? [])
              .map((e) => Stock.fromJson(e as Map<String, dynamic>))
              .toList(),
          'losers': (data['losers'] as List? ?? [])
              .map((e) => Stock.fromJson(e as Map<String, dynamic>))
              .toList(),
        };
      }
      return _mockGainersLosers();
    } catch (_) {
      return _mockGainersLosers();
    }
  }

  // GET /categories
  static Future<List<Map<String, dynamic>>> getCategories() async {
    try {
      final uri = Uri.parse('$_baseUrl/api/categories');
      final response = await _client
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data is List) {
          return data.cast<Map<String, dynamic>>();
        }
      }
    } catch (_) {}

    return [
      {'id': 'nifty50', 'name': 'NIFTY 50'},
      {'id': 'banknifty', 'name': 'Bank'},
      {'id': 'it', 'name': 'IT'},
      {'id': 'pharma', 'name': 'Pharma'},
      {'id': 'auto', 'name': 'Auto'},
      {'id': 'fmcg', 'name': 'FMCG'},
      {'id': 'metal', 'name': 'Metal'},
      {'id': 'realty', 'name': 'Realty'},
    ];
  }

  // GET /stock/:symbol
  static Future<Map<String, dynamic>> getStockDetail(String symbol) async {
    try {
      final uri =
          Uri.parse('$_baseUrl/api/stock/${Uri.encodeComponent(symbol)}');
      final response = await _client
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {};
  }

  // GET /portfolio
  static Future<Map<String, dynamic>> getPortfolio() async {
    try {
      final uri = Uri.parse('$_baseUrl/api/paper/portfolio');
      final response = await _client
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return _mockPortfolio();
  }

  // POST /buy
  static Future<Map<String, dynamic>> executeBuy(
      String symbol, int qty) async {
    try {
      final uri = Uri.parse('$_baseUrl/api/paper/buy');
      final response = await _client
          .post(uri,
              headers: _headers,
              body: jsonEncode({'symbol': symbol, 'quantity': qty}))
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      final err = jsonDecode(response.body);
      return {
        'success': false,
        'message': err['message'] ?? err['error'] ?? 'Order failed'
      };
    } catch (e) {
      return {'success': false, 'message': 'Connection error: $e'};
    }
  }

  // POST /sell
  static Future<Map<String, dynamic>> executeSell(
      String symbol, int qty) async {
    try {
      final uri = Uri.parse('$_baseUrl/api/paper/sell');
      final response = await _client
          .post(uri,
              headers: _headers,
              body: jsonEncode({'symbol': symbol, 'quantity': qty}))
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      final err = jsonDecode(response.body);
      return {
        'success': false,
        'message': err['message'] ?? err['error'] ?? 'Order failed'
      };
    } catch (e) {
      return {'success': false, 'message': 'Connection error: $e'};
    }
  }

  // POST /reset
  static Future<Map<String, dynamic>> resetPortfolio() async {
    try {
      final uri = Uri.parse('$_baseUrl/api/paper/reset');
      final response = await _client
          .post(uri, headers: _headers)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {'success': true, 'message': 'Portfolio reset'};
  }

  // GET /trades
  static Future<List<Trade>> getTradeHistory() async {
    try {
      final uri = Uri.parse('$_baseUrl/api/paper/history');
      final response = await _client
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        List<dynamic> items =
            data is List ? data : (data['trades'] as List? ?? []);
        return items
            .map((e) => Trade.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {}
    return [];
  }

  // GET positions from portfolio
  static Future<List<Position>> getPositions() async {
    try {
      final portfolio = await getPortfolio();
      final positions = portfolio['positions'] as List? ??
          portfolio['holdings'] as List? ??
          [];
      return positions
          .map((e) => Position.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  // Detect local IP for mobile testing
  static Future<String> detectLocalIp() async {
    return 'localhost';
  }

  // ─── Mock data (20 realistic Indian stocks) ───────────────────────────────

  static List<Stock> _mockStocks(String category) {
    final all = [
      Stock(
          symbol: 'RELIANCE',
          name: 'Reliance Industries',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 2847.50,
          change: 1.23,
          score: 72.5,
          rsi: 58.3,
          stopLoss: 2790.0,
          target: 2950.0,
          riskReward: 1.8),
      Stock(
          symbol: 'TCS',
          name: 'Tata Consultancy Services',
          direction: 'HOLD',
          trend: 'NEUTRAL',
          volatility: 'LOW',
          macd: 'NEUTRAL',
          price: 3620.80,
          change: -0.45,
          score: 48.2,
          rsi: 52.1,
          stopLoss: 3550.0,
          target: 3750.0,
          riskReward: 1.3),
      Stock(
          symbol: 'HDFCBANK',
          name: 'HDFC Bank',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'MEDIUM',
          macd: 'BULLISH',
          price: 1678.90,
          change: 2.10,
          score: 68.7,
          rsi: 61.5,
          stopLoss: 1640.0,
          target: 1760.0,
          riskReward: 2.1),
      Stock(
          symbol: 'INFY',
          name: 'Infosys',
          direction: 'AVOID',
          trend: 'BEARISH',
          volatility: 'MEDIUM',
          macd: 'BEARISH',
          price: 1432.60,
          change: -1.87,
          score: 28.4,
          rsi: 38.9,
          stopLoss: 1480.0,
          target: 1350.0,
          riskReward: 0.8),
      Stock(
          symbol: 'ICICIBANK',
          name: 'ICICI Bank',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 1089.45,
          change: 1.65,
          score: 75.3,
          rsi: 63.2,
          stopLoss: 1060.0,
          target: 1145.0,
          riskReward: 1.9),
      Stock(
          symbol: 'SBIN',
          name: 'State Bank of India',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'MEDIUM',
          macd: 'BULLISH',
          price: 762.15,
          change: 0.89,
          score: 63.8,
          rsi: 57.4,
          stopLoss: 742.0,
          target: 802.0,
          riskReward: 1.6),
      Stock(
          symbol: 'WIPRO',
          name: 'Wipro Ltd',
          direction: 'HOLD',
          trend: 'NEUTRAL',
          volatility: 'MEDIUM',
          macd: 'NEUTRAL',
          price: 476.30,
          change: 0.30,
          score: 44.1,
          rsi: 49.7,
          stopLoss: 462.0,
          target: 498.0,
          riskReward: 1.5),
      Stock(
          symbol: 'HINDUNILVR',
          name: 'Hindustan Unilever',
          direction: 'HOLD',
          trend: 'NEUTRAL',
          volatility: 'LOW',
          macd: 'NEUTRAL',
          price: 2310.70,
          change: -0.21,
          score: 50.6,
          rsi: 51.3,
          stopLoss: 2270.0,
          target: 2380.0,
          riskReward: 1.2),
      Stock(
          symbol: 'AXISBANK',
          name: 'Axis Bank',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'MEDIUM',
          macd: 'BULLISH',
          price: 1087.60,
          change: 1.42,
          score: 66.4,
          rsi: 60.1,
          stopLoss: 1058.0,
          target: 1145.0,
          riskReward: 1.9),
      Stock(
          symbol: 'BHARTIARTL',
          name: 'Bharti Airtel',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 1438.20,
          change: 0.78,
          score: 69.2,
          rsi: 59.8,
          stopLoss: 1405.0,
          target: 1510.0,
          riskReward: 2.0),
      Stock(
          symbol: 'TATAMOTORS',
          name: 'Tata Motors',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'HIGH',
          macd: 'BULLISH',
          price: 952.40,
          change: 2.34,
          score: 71.8,
          rsi: 64.2,
          stopLoss: 920.0,
          target: 1010.0,
          riskReward: 1.8),
      Stock(
          symbol: 'LTIM',
          name: 'LTI Mindtree',
          direction: 'AVOID',
          trend: 'BEARISH',
          volatility: 'HIGH',
          macd: 'BEARISH',
          price: 4987.20,
          change: -2.09,
          score: 26.7,
          rsi: 36.4,
          stopLoss: 5150.0,
          target: 4700.0,
          riskReward: 0.7),
      Stock(
          symbol: 'MARUTI',
          name: 'Maruti Suzuki',
          direction: 'HOLD',
          trend: 'NEUTRAL',
          volatility: 'LOW',
          macd: 'NEUTRAL',
          price: 12140.00,
          change: 0.15,
          score: 52.3,
          rsi: 53.0,
          stopLoss: 11850.0,
          target: 12480.0,
          riskReward: 1.2),
      Stock(
          symbol: 'SUNPHARMA',
          name: 'Sun Pharmaceutical',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 1589.75,
          change: 1.05,
          score: 67.1,
          rsi: 58.6,
          stopLoss: 1555.0,
          target: 1660.0,
          riskReward: 2.0),
      Stock(
          symbol: 'ADANIENT',
          name: 'Adani Enterprises',
          direction: 'HOLD',
          trend: 'NEUTRAL',
          volatility: 'HIGH',
          macd: 'NEUTRAL',
          price: 2934.80,
          change: -0.65,
          score: 42.5,
          rsi: 47.2,
          stopLoss: 2860.0,
          target: 3060.0,
          riskReward: 1.7),
      Stock(
          symbol: 'KOTAKBANK',
          name: 'Kotak Mahindra Bank',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 1812.30,
          change: 0.94,
          score: 62.8,
          rsi: 56.3,
          stopLoss: 1770.0,
          target: 1900.0,
          riskReward: 2.1),
      Stock(
          symbol: 'NTPC',
          name: 'NTPC Ltd',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 358.90,
          change: 2.87,
          score: 66.1,
          rsi: 60.8,
          stopLoss: 348.0,
          target: 378.0,
          riskReward: 1.9),
      Stock(
          symbol: 'TECHM',
          name: 'Tech Mahindra',
          direction: 'AVOID',
          trend: 'BEARISH',
          volatility: 'MEDIUM',
          macd: 'BEARISH',
          price: 1312.50,
          change: -2.84,
          score: 27.8,
          rsi: 37.2,
          stopLoss: 1360.0,
          target: 1240.0,
          riskReward: 0.6),
      Stock(
          symbol: 'POWERGRID',
          name: 'Power Grid Corp',
          direction: 'BUY',
          trend: 'BULLISH',
          volatility: 'LOW',
          macd: 'BULLISH',
          price: 287.40,
          change: 1.43,
          score: 64.7,
          rsi: 59.5,
          stopLoss: 279.0,
          target: 302.0,
          riskReward: 1.9),
      Stock(
          symbol: 'BAJFINANCE',
          name: 'Bajaj Finance',
          direction: 'AVOID',
          trend: 'BEARISH',
          volatility: 'HIGH',
          macd: 'BEARISH',
          price: 6842.30,
          change: -3.21,
          score: 24.5,
          rsi: 35.6,
          stopLoss: 7000.0,
          target: 6500.0,
          riskReward: 0.7),
    ];

    // Filter by category if possible; otherwise return all
    switch (category.toLowerCase()) {
      case 'banknifty':
        return all
            .where((s) => [
                  'HDFCBANK',
                  'ICICIBANK',
                  'SBIN',
                  'AXISBANK',
                  'KOTAKBANK'
                ].contains(s.symbol))
            .toList();
      case 'it':
        return all
            .where((s) =>
                ['TCS', 'INFY', 'WIPRO', 'TECHM', 'LTIM'].contains(s.symbol))
            .toList();
      case 'pharma':
        return all
            .where((s) => ['SUNPHARMA'].contains(s.symbol))
            .toList();
      case 'auto':
        return all
            .where(
                (s) => ['TATAMOTORS', 'MARUTI'].contains(s.symbol))
            .toList();
      default:
        return all;
    }
  }

  static Map<String, List<Stock>> _mockGainersLosers() {
    return {
      'gainers': [
        Stock(
            symbol: 'TATASTEEL',
            name: 'Tata Steel',
            direction: 'BUY',
            trend: 'BULLISH',
            volatility: 'HIGH',
            macd: 'BULLISH',
            price: 142.85,
            change: 4.32,
            score: 71.2,
            rsi: 65.0,
            stopLoss: 136.0,
            target: 152.0,
            riskReward: 1.7),
        Stock(
            symbol: 'TATAMOTORS',
            name: 'Tata Motors',
            direction: 'BUY',
            trend: 'BULLISH',
            volatility: 'HIGH',
            macd: 'BULLISH',
            price: 952.40,
            change: 3.42,
            score: 71.8,
            rsi: 64.2,
            stopLoss: 920.0,
            target: 1010.0,
            riskReward: 1.8),
        Stock(
            symbol: 'COALINDIA',
            name: 'Coal India',
            direction: 'BUY',
            trend: 'BULLISH',
            volatility: 'MEDIUM',
            macd: 'BULLISH',
            price: 421.60,
            change: 3.15,
            score: 68.4,
            rsi: 62.3,
            stopLoss: 408.0,
            target: 445.0,
            riskReward: 1.8),
        Stock(
            symbol: 'NTPC',
            name: 'NTPC Ltd',
            direction: 'BUY',
            trend: 'BULLISH',
            volatility: 'LOW',
            macd: 'BULLISH',
            price: 358.90,
            change: 2.87,
            score: 66.1,
            rsi: 60.8,
            stopLoss: 348.0,
            target: 378.0,
            riskReward: 1.9),
        Stock(
            symbol: 'JSWSTEEL',
            name: 'JSW Steel',
            direction: 'BUY',
            trend: 'BULLISH',
            volatility: 'HIGH',
            macd: 'BULLISH',
            price: 874.50,
            change: 2.18,
            score: 62.3,
            rsi: 58.2,
            stopLoss: 852.0,
            target: 920.0,
            riskReward: 2.1),
        Stock(
            symbol: 'BHARTIARTL',
            name: 'Bharti Airtel',
            direction: 'BUY',
            trend: 'BULLISH',
            volatility: 'LOW',
            macd: 'BULLISH',
            price: 1438.20,
            change: 1.92,
            score: 69.2,
            rsi: 59.8,
            stopLoss: 1405.0,
            target: 1510.0,
            riskReward: 2.0),
      ],
      'losers': [
        Stock(
            symbol: 'BAJFINANCE',
            name: 'Bajaj Finance',
            direction: 'AVOID',
            trend: 'BEARISH',
            volatility: 'HIGH',
            macd: 'BEARISH',
            price: 6842.30,
            change: -3.21,
            score: 24.5,
            rsi: 35.6,
            stopLoss: 7000.0,
            target: 6500.0,
            riskReward: 0.7),
        Stock(
            symbol: 'TECHM',
            name: 'Tech Mahindra',
            direction: 'AVOID',
            trend: 'BEARISH',
            volatility: 'MEDIUM',
            macd: 'BEARISH',
            price: 1312.50,
            change: -2.84,
            score: 27.8,
            rsi: 37.2,
            stopLoss: 1360.0,
            target: 1240.0,
            riskReward: 0.6),
        Stock(
            symbol: 'HCLTECH',
            name: 'HCL Technologies',
            direction: 'AVOID',
            trend: 'BEARISH',
            volatility: 'MEDIUM',
            macd: 'BEARISH',
            price: 1589.70,
            change: -2.46,
            score: 30.2,
            rsi: 39.1,
            stopLoss: 1640.0,
            target: 1500.0,
            riskReward: 0.8),
        Stock(
            symbol: 'LTIM',
            name: 'LTI Mindtree',
            direction: 'AVOID',
            trend: 'BEARISH',
            volatility: 'HIGH',
            macd: 'BEARISH',
            price: 4987.20,
            change: -2.09,
            score: 26.7,
            rsi: 36.4,
            stopLoss: 5150.0,
            target: 4700.0,
            riskReward: 0.7),
        Stock(
            symbol: 'INFY',
            name: 'Infosys',
            direction: 'AVOID',
            trend: 'BEARISH',
            volatility: 'MEDIUM',
            macd: 'BEARISH',
            price: 1432.60,
            change: -1.87,
            score: 28.4,
            rsi: 38.9,
            stopLoss: 1480.0,
            target: 1350.0,
            riskReward: 0.8),
        Stock(
            symbol: 'MPHASIS',
            name: 'Mphasis Ltd',
            direction: 'AVOID',
            trend: 'BEARISH',
            volatility: 'MEDIUM',
            macd: 'BEARISH',
            price: 2341.80,
            change: -1.92,
            score: 31.4,
            rsi: 40.3,
            stopLoss: 2420.0,
            target: 2200.0,
            riskReward: 0.9),
      ],
    };
  }

  static Map<String, dynamic> _mockPortfolio() {
    return {
      'cash': 1000000.0,
      'portfolio_value': 1000000.0,
      'total_invested': 0.0,
      'total_pnl': 0.0,
      'total_pnl_pct': 0.0,
      'positions': [],
      'total_trades': 0,
      'win_trades': 0,
      'loss_trades': 0,
    };
  }
}
