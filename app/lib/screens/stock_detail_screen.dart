import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/stock.dart';
import '../theme/app_theme.dart';
import '../widgets/score_ring.dart';
import '../widgets/direction_badge.dart';

class StockDetailScreen extends StatelessWidget {
  final Stock stock;

  const StockDetailScreen({super.key, required this.stock});

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,##,##0.00', 'en_IN');
    final changeColor = stock.change >= 0 ? AppColors.green : AppColors.red;
    final changeBg = stock.change >= 0 ? AppColors.greenSurface : AppColors.redSurface;
    final changeStr =
        '${stock.change >= 0 ? '+' : ''}${stock.change.toStringAsFixed(2)}%';
    final scoreColor = AppTheme.scoreColor(stock.score);
    final avatarColor = AppTheme.avatarColor(stock.symbol);
    final initials = _initials(stock.symbol);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new,
              color: AppColors.textSecondary, size: 18),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              stock.symbol,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
            Text(
              stock.name,
              style: const TextStyle(
                fontSize: 11,
                color: AppColors.textMuted,
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
      body: Stack(
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Price hero ──
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    // Avatar
                    Container(
                      width: 52,
                      height: 52,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: avatarColor.withValues(alpha: 0.18),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        initials,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: avatarColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '₹${fmt.format(stock.price)}',
                            style: const TextStyle(
                              fontSize: 30,
                              fontWeight: FontWeight.w700,
                              color: AppColors.textPrimary,
                              letterSpacing: -0.5,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: changeBg,
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      stock.change >= 0
                                          ? Icons.arrow_upward
                                          : Icons.arrow_downward,
                                      size: 11,
                                      color: changeColor,
                                    ),
                                    const SizedBox(width: 3),
                                    Text(
                                      changeStr,
                                      style: TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: changeColor,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Text(
                                'Today',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textMuted,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 24),

                // ── AI Score section ──
                _sectionLabel('AI ANALYSIS'),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: AppColors.card,
                    borderRadius: BorderRadius.circular(16),
                    border:
                        Border.all(color: AppColors.border, width: 0.5),
                  ),
                  child: Row(
                    children: [
                      // Large score ring
                      ScoreRing(score: stock.score, size: 80, strokeWidth: 5),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Profit Probability',
                              style: TextStyle(
                                fontSize: 12,
                                color: AppColors.textMuted,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${stock.score.toStringAsFixed(1)}%',
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w700,
                                color: scoreColor,
                              ),
                            ),
                            const SizedBox(height: 8),
                            DirectionBadge(
                                direction: stock.direction, fontSize: 11),
                            const SizedBox(height: 6),
                            Text(
                              _scoreDescription(stock.score),
                              style: const TextStyle(
                                fontSize: 11,
                                color: AppColors.textSecondary,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                // ── Technical indicators grid ──
                _sectionLabel('TECHNICAL INDICATORS'),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                        child: _indicatorCard('RSI',
                            stock.rsi.toStringAsFixed(1), _rsiLabel(stock.rsi),
                            _rsiColor(stock.rsi))),
                    const SizedBox(width: 10),
                    Expanded(
                        child: _indicatorCard(
                            'MACD', stock.macd, stock.macd,
                            _trendColor(stock.macd))),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                        child: _indicatorCard('Trend', stock.trend, stock.trend,
                            _trendColor(stock.trend))),
                    const SizedBox(width: 10),
                    Expanded(
                        child: _indicatorCard(
                            'Volatility', stock.volatility, stock.volatility,
                            _volatilityColor(stock.volatility))),
                  ],
                ),

                const SizedBox(height: 20),

                // ── Price levels ──
                _sectionLabel('PRICE LEVELS'),
                const SizedBox(height: 12),
                Container(
                  decoration: BoxDecoration(
                    color: AppColors.card,
                    borderRadius: BorderRadius.circular(16),
                    border:
                        Border.all(color: AppColors.border, width: 0.5),
                  ),
                  child: Column(
                    children: [
                      _levelRow('Stop Loss', '₹${fmt.format(stock.stopLoss)}',
                          AppColors.red, Icons.shield_outlined, true),
                      const Divider(
                          height: 0.5,
                          color: AppColors.border,
                          indent: 16,
                          endIndent: 16),
                      _levelRow('Target Price', '₹${fmt.format(stock.target)}',
                          AppColors.green, Icons.flag_outlined, false),
                      const Divider(
                          height: 0.5,
                          color: AppColors.border,
                          indent: 16,
                          endIndent: 16),
                      _levelRow(
                          'Risk / Reward',
                          '${stock.riskReward.toStringAsFixed(2)}x',
                          stock.riskReward >= 1.5
                              ? AppColors.green
                              : AppColors.amber,
                          Icons.balance_outlined,
                          false),
                    ],
                  ),
                ),

                const SizedBox(height: 16),

                // ── Disclaimer ──
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.amber.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                        color: AppColors.amber.withValues(alpha: 0.2)),
                  ),
                  child: const Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.info_outline,
                          color: AppColors.amber, size: 14),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'AI predictions are for educational purposes only. This is a demo app with no real money involved.',
                          style: TextStyle(
                            fontSize: 10.5,
                            color: AppColors.amber,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // ── Sticky BUY / SELL bar ──
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              decoration: BoxDecoration(
                color: AppColors.background,
                border: const Border(
                    top: BorderSide(color: AppColors.border, width: 0.5)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {},
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.green,
                        foregroundColor: Colors.black,
                        padding:
                            const EdgeInsets.symmetric(vertical: 15),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        elevation: 0,
                      ),
                      child: const Text(
                        'BUY',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {},
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.red,
                        foregroundColor: Colors.white,
                        padding:
                            const EdgeInsets.symmetric(vertical: 15),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        elevation: 0,
                      ),
                      child: const Text(
                        'SELL',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionLabel(String label) {
    return Text(
      label,
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        color: AppColors.textMuted,
        letterSpacing: 1,
      ),
    );
  }

  Widget _indicatorCard(
      String label, String value, String status, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              color: AppColors.textMuted,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: _progressValue(label, value),
            backgroundColor: AppColors.border,
            valueColor: AlwaysStoppedAnimation(color),
            minHeight: 3,
            borderRadius: BorderRadius.circular(2),
          ),
        ],
      ),
    );
  }

  Widget _levelRow(
      String label, String value, Color color, IconData icon, bool isFirst) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.1),
            ),
            child: Icon(icon, color: color, size: 16),
          ),
          const SizedBox(width: 12),
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  String _initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, name.length.clamp(0, 2)).toUpperCase();
  }

  String _scoreDescription(double score) {
    if (score >= 65) return 'Strong buy signal. High probability of upward movement.';
    if (score >= 45) return 'Hold position. Mixed signals, wait for confirmation.';
    return 'Weak signal. Consider avoiding or exiting position.';
  }

  double _progressValue(String label, String value) {
    if (label == 'RSI') {
      final rsi = double.tryParse(value) ?? 50;
      return (rsi / 100).clamp(0.0, 1.0);
    }
    return 0.5;
  }

  Color _trendColor(String trend) {
    switch (trend.toUpperCase()) {
      case 'BULLISH':
        return AppColors.green;
      case 'BEARISH':
        return AppColors.red;
      default:
        return AppColors.amber;
    }
  }

  Color _rsiColor(double rsi) {
    if (rsi > 70) return AppColors.red;
    if (rsi < 30) return AppColors.green;
    return AppColors.amber;
  }

  String _rsiLabel(double rsi) {
    if (rsi > 70) return 'Overbought';
    if (rsi < 30) return 'Oversold';
    return 'Neutral';
  }

  Color _volatilityColor(String v) {
    switch (v.toUpperCase()) {
      case 'LOW':
        return AppColors.green;
      case 'HIGH':
        return AppColors.red;
      default:
        return AppColors.amber;
    }
  }
}
