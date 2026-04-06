import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/stock.dart';
import '../theme/app_theme.dart';
import 'score_ring.dart';
import 'direction_badge.dart';

class StockCard extends StatelessWidget {
  final Stock stock;
  final VoidCallback? onTap;
  // compact kept for API compatibility but unused now
  final bool compact;

  const StockCard({
    super.key,
    required this.stock,
    this.onTap,
    this.compact = false,
  });

  String _initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, name.length.clamp(0, 2)).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final priceFormat = NumberFormat('#,##,##0.00', 'en_IN');
    final changeColor = stock.change >= 0 ? AppColors.green : AppColors.red;
    final changeBg = stock.change >= 0 ? AppColors.greenSurface : AppColors.redSurface;
    final changeStr =
        '${stock.change >= 0 ? '+' : ''}${stock.change.toStringAsFixed(2)}%';
    final avatarColor = AppTheme.avatarColor(stock.symbol);

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(0),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            // Circle avatar with initials
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: avatarColor.withValues(alpha: 0.18),
              ),
              alignment: Alignment.center,
              child: Text(
                _initials(stock.symbol),
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: avatarColor,
                  letterSpacing: 0.5,
                ),
              ),
            ),

            const SizedBox(width: 12),

            // Name column
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    stock.symbol,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                      letterSpacing: 0.1,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    stock.name,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w400,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),

            const SizedBox(width: 12),

            // Price column
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '₹${priceFormat.format(stock.price)}',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 3),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: changeBg,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    changeStr,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: changeColor,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(width: 12),

            // Score ring + direction
            Column(
              children: [
                ScoreRing(score: stock.score, size: 36, strokeWidth: 2.5),
                const SizedBox(height: 3),
                DirectionBadge(direction: stock.direction, fontSize: 8),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
