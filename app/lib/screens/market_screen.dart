import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shimmer/shimmer.dart';
import 'package:intl/intl.dart';
import '../theme/app_theme.dart';
import '../providers/stock_provider.dart';
import '../models/stock.dart';
import '../widgets/direction_badge.dart';
import 'stock_detail_screen.dart';

class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen>
    with AutomaticKeepAliveClientMixin {
  bool _showGainers = true;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<StockProvider>().loadGainersLosers();
    });
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final sp = context.watch<StockProvider>();
    final stocks = _showGainers ? sp.gainers : sp.losers;

    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Row(
              children: [
                const Text(
                  'Markets',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                    letterSpacing: -0.5,
                  ),
                ),
                const Spacer(),
                GestureDetector(
                  onTap: () => sp.loadGainersLosers(),
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.card,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.border, width: 0.5),
                    ),
                    child: const Icon(Icons.refresh,
                        color: AppColors.textMuted, size: 18),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Segmented toggle — SegmentedButton style
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border, width: 0.5),
              ),
              child: Row(
                children: [
                  _buildSegment('Top Gainers', true, AppColors.green),
                  _buildSegment('Top Losers', false, AppColors.red),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Column headers
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Row(
              children: [
                SizedBox(
                  width: 28,
                  child: Text(
                    '#',
                    style: TextStyle(
                      fontSize: 10,
                      color: AppColors.textMuted,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'STOCK',
                    style: TextStyle(
                      fontSize: 10,
                      color: AppColors.textMuted,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
                const Text(
                  'CHANGE',
                  style: TextStyle(
                    fontSize: 10,
                    color: AppColors.textMuted,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.8,
                  ),
                ),
                const SizedBox(width: 12),
                const SizedBox(
                  width: 72,
                  child: Text(
                    'PRICE',
                    textAlign: TextAlign.right,
                    style: TextStyle(
                      fontSize: 10,
                      color: AppColors.textMuted,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
              ],
            ),
          ),

          const Divider(height: 0.5, color: AppColors.border),

          // Stock list
          Expanded(
            child: sp.isLoading
                ? _buildShimmer()
                : stocks.isEmpty
                    ? _buildEmpty()
                    : RefreshIndicator(
                        color: AppColors.cyan,
                        backgroundColor: AppColors.card,
                        onRefresh: () => sp.loadGainersLosers(),
                        child: ListView.separated(
                          padding: const EdgeInsets.only(bottom: 24),
                          itemCount: stocks.length,
                          separatorBuilder: (_, __) => const Divider(
                            height: 0.5,
                            color: AppColors.border,
                            indent: 52,
                          ),
                          itemBuilder: (context, i) =>
                              _buildStockRow(context, stocks[i], i + 1),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildSegment(String label, bool isGainers, Color activeColor) {
    final isSelected = _showGainers == isGainers;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _showGainers = isGainers),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          margin: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            color: isSelected ? activeColor.withValues(alpha: 0.12) : Colors.transparent,
            borderRadius: BorderRadius.circular(9),
            border: isSelected
                ? Border.all(color: activeColor.withValues(alpha: 0.35), width: 1)
                : null,
          ),
          alignment: Alignment.center,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                isGainers ? Icons.trending_up : Icons.trending_down,
                size: 15,
                color: isSelected ? activeColor : AppColors.textMuted,
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected ? activeColor : AppColors.textMuted,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStockRow(BuildContext context, Stock stock, int rank) {
    final fmt = NumberFormat('#,##,##0.00', 'en_IN');
    final changeColor = stock.change >= 0 ? AppColors.green : AppColors.red;
    final changeBg = stock.change >= 0 ? AppColors.greenSurface : AppColors.redSurface;
    final changeStr = '${stock.change >= 0 ? '+' : ''}${stock.change.toStringAsFixed(2)}%';

    return InkWell(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => StockDetailScreen(stock: stock)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            // Rank
            SizedBox(
              width: 28,
              child: Text(
                '$rank',
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textMuted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Stock info
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
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    stock.name,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textMuted,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            // Change badge — prominent
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: changeBg,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                changeStr,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: changeColor,
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Price
            SizedBox(
              width: 72,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '₹${fmt.format(stock.price)}',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  DirectionBadge(direction: stock.direction, fontSize: 8),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildShimmer() {
    return ListView.separated(
      itemCount: 8,
      separatorBuilder: (_, __) =>
          const Divider(height: 0.5, color: AppColors.border),
      itemBuilder: (_, __) => Shimmer.fromColors(
        baseColor: AppColors.card,
        highlightColor: AppColors.cardElevated,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Container(width: 28, height: 12, color: AppColors.card),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(height: 12, width: 80, color: AppColors.card),
                    const SizedBox(height: 4),
                    Container(height: 10, width: 120, color: AppColors.card),
                  ],
                ),
              ),
              Container(
                  height: 28, width: 60, color: AppColors.card),
              const SizedBox(width: 12),
              Container(height: 12, width: 70, color: AppColors.card),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmpty() {
    return const Center(
      child: Text(
        'No data available',
        style: TextStyle(color: AppColors.textMuted, fontSize: 14),
      ),
    );
  }
}
