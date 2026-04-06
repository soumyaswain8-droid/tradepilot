import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../theme/app_theme.dart';
import '../providers/stock_provider.dart';
import '../models/stock.dart';
import '../models/position.dart';
import '../models/trade.dart';
import '../widgets/score_ring.dart';
import '../widgets/direction_badge.dart';

class TradeScreen extends StatefulWidget {
  const TradeScreen({super.key});

  @override
  State<TradeScreen> createState() => _TradeScreenState();
}

class _TradeScreenState extends State<TradeScreen>
    with AutomaticKeepAliveClientMixin, SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _searchController = TextEditingController();
  final _qtyController = TextEditingController(text: '1');
  Stock? _selectedStock;
  List<Stock> _searchResults = [];
  bool _isSearching = false;
  bool _isExecuting = false;
  String? _tradeMessage;
  bool _tradeSuccess = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<StockProvider>().loadPortfolio();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    _qtyController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    final sp = context.read<StockProvider>();
    setState(() {
      _isSearching = query.isNotEmpty;
      _searchResults = sp.searchStocks(query);
    });
  }

  void _selectStock(Stock stock) {
    setState(() {
      _selectedStock = stock;
      _isSearching = false;
      _searchController.text = stock.symbol;
      _tradeMessage = null;
    });
  }

  Future<void> _executeTrade(bool isBuy) async {
    if (_selectedStock == null) return;
    final qty = int.tryParse(_qtyController.text) ?? 0;
    if (qty <= 0) {
      setState(() {
        _tradeMessage = 'Enter a valid quantity';
        _tradeSuccess = false;
      });
      return;
    }

    setState(() {
      _isExecuting = true;
      _tradeMessage = null;
    });

    final sp = context.read<StockProvider>();
    final result = isBuy
        ? await sp.executeBuy(_selectedStock!.symbol, qty)
        : await sp.executeSell(_selectedStock!.symbol, qty);

    setState(() {
      _isExecuting = false;
      _tradeSuccess =
          result['success'] == true || result['status'] == 'success';
      _tradeMessage = result['message']?.toString() ??
          (_tradeSuccess
              ? '${isBuy ? 'Bought' : 'Sold'} $qty shares of ${_selectedStock!.symbol}'
              : 'Trade failed');
    });
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final sp = context.watch<StockProvider>();
    final fmt = NumberFormat('#,##,##0.00', 'en_IN');
    final total = _selectedStock != null
        ? _selectedStock!.price * (int.tryParse(_qtyController.text) ?? 1)
        : 0.0;
    final pnlColor = sp.totalPnl >= 0 ? AppColors.green : AppColors.red;

    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Row(
              children: [
                const Text(
                  'Trade',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                    letterSpacing: -0.5,
                  ),
                ),
                const Spacer(),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    const Text(
                      'Available',
                      style: TextStyle(
                          fontSize: 10, color: AppColors.textMuted),
                    ),
                    Text(
                      '₹${_formatLakh(sp.availableCash)}',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppColors.green,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // ── Portfolio summary card with gradient ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    const Color(0xFF0F2040),
                    AppColors.cyanDim.withValues(alpha: 0.25),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                    color: AppColors.cyan.withValues(alpha: 0.2), width: 0.5),
              ),
              child: Column(
                children: [
                  // Total portfolio value
                  Text(
                    '₹${_formatLakh(sp.portfolioValue)}',
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 2),
                  const Text(
                    'Total Portfolio Value',
                    style: TextStyle(
                      fontSize: 11,
                      color: AppColors.textMuted,
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Stats row
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _miniStat('Cash',
                          '₹${_formatLakh(sp.availableCash)}',
                          AppColors.cyan),
                      _vertDivider(),
                      _miniStat(
                        'P&L',
                        '${sp.totalPnl >= 0 ? '+' : ''}₹${_formatLakh(sp.totalPnl.abs())}',
                        pnlColor,
                      ),
                      _vertDivider(),
                      _miniStat(
                        'Win / Loss',
                        '${sp.winTrades} / ${sp.lossTrades}',
                        AppColors.textSecondary,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // ── Tab bar ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              height: 42,
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border, width: 0.5),
              ),
              child: TabBar(
                controller: _tabController,
                indicator: BoxDecoration(
                  color: AppColors.cyan.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: AppColors.cyan.withValues(alpha: 0.4)),
                ),
                dividerColor: Colors.transparent,
                labelColor: AppColors.cyan,
                unselectedLabelColor: AppColors.textMuted,
                labelStyle: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600),
                unselectedLabelStyle:
                    const TextStyle(fontSize: 13),
                tabs: const [
                  Tab(text: 'Place Order'),
                  Tab(text: 'History'),
                ],
              ),
            ),
          ),

          const SizedBox(height: 12),

          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildOrderTab(sp, fmt, total),
                _buildHistoryTab(sp.trades, fmt),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _miniStat(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
        ),
      ],
    );
  }

  Widget _vertDivider() {
    return Container(height: 30, width: 0.5, color: AppColors.border);
  }

  Widget _buildOrderTab(StockProvider sp, NumberFormat fmt, double total) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Search field
          Container(
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border, width: 0.5),
            ),
            child: Row(
              children: [
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12),
                  child: Icon(Icons.search, color: AppColors.textMuted, size: 18),
                ),
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                    decoration: const InputDecoration(
                      hintText: 'Search stock (e.g. RELIANCE)',
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      isDense: true,
                      contentPadding:
                          EdgeInsets.symmetric(vertical: 14),
                      hintStyle: TextStyle(
                        color: AppColors.textMuted,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                    onChanged: _onSearchChanged,
                  ),
                ),
                if (_searchController.text.isNotEmpty)
                  GestureDetector(
                    onTap: () {
                      _searchController.clear();
                      setState(() {
                        _isSearching = false;
                        _selectedStock = null;
                      });
                    },
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 12),
                      child: Icon(Icons.close,
                          color: AppColors.textMuted, size: 16),
                    ),
                  ),
              ],
            ),
          ),

          // Search results
          if (_isSearching && _searchResults.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(top: 4),
              decoration: BoxDecoration(
                color: AppColors.cardElevated,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border, width: 0.5),
              ),
              constraints: const BoxConstraints(maxHeight: 200),
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: _searchResults.length.clamp(0, 6),
                separatorBuilder: (_, __) =>
                    const Divider(height: 0.5, color: AppColors.border),
                itemBuilder: (context, i) {
                  final s = _searchResults[i];
                  return ListTile(
                    dense: true,
                    onTap: () => _selectStock(s),
                    title: Text(
                      s.symbol,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    subtitle: Text(
                      s.name,
                      style: const TextStyle(
                          fontSize: 10, color: AppColors.textMuted),
                    ),
                    trailing: Text(
                      '₹${fmt.format(s.price)}',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  );
                },
              ),
            ),

          // Selected stock card
          if (_selectedStock != null) ...[
            const SizedBox(height: 16),
            _buildSelectedStockCard(fmt),
            const SizedBox(height: 16),

            // Quantity + Total row
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'QUANTITY',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textMuted,
                          letterSpacing: 0.8,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _qtyController,
                        keyboardType: TextInputType.number,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly
                        ],
                        onChanged: (_) => setState(() {}),
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary,
                        ),
                        decoration: const InputDecoration(
                          hintText: '1',
                          contentPadding: EdgeInsets.symmetric(
                              horizontal: 14, vertical: 12),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'TOTAL COST',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textMuted,
                          letterSpacing: 0.8,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Container(
                        height: 50,
                        padding: const EdgeInsets.symmetric(horizontal: 14),
                        decoration: BoxDecoration(
                          color: AppColors.card,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                              color: AppColors.border, width: 0.5),
                        ),
                        alignment: Alignment.centerLeft,
                        child: Text(
                          '₹${fmt.format(total)}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppColors.cyan,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Trade message
            if (_tradeMessage != null)
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 10),
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: (_tradeSuccess ? AppColors.green : AppColors.red)
                      .withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: (_tradeSuccess ? AppColors.green : AppColors.red)
                        .withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      _tradeSuccess
                          ? Icons.check_circle_outline
                          : Icons.error_outline,
                      color:
                          _tradeSuccess ? AppColors.green : AppColors.red,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _tradeMessage!,
                        style: TextStyle(
                          fontSize: 12,
                          color: _tradeSuccess
                              ? AppColors.green
                              : AppColors.red,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            // BUY / SELL buttons
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed:
                        _isExecuting ? null : () => _executeTrade(true),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.green,
                      foregroundColor: Colors.black,
                      padding:
                          const EdgeInsets.symmetric(vertical: 15),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _isExecuting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor:
                                  AlwaysStoppedAnimation(Colors.black),
                            ),
                          )
                        : const Text(
                            'BUY',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 1,
                            ),
                          ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton(
                    onPressed:
                        _isExecuting ? null : () => _executeTrade(false),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.red,
                      foregroundColor: Colors.white,
                      padding:
                          const EdgeInsets.symmetric(vertical: 15),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
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
          ],

          // Holdings section
          if (sp.positions.isNotEmpty) ...[
            const SizedBox(height: 28),
            const Text(
              'HOLDINGS',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppColors.textMuted,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            ...sp.positions.map((p) => _buildPositionRow(p, fmt)),
          ],
        ],
      ),
    );
  }

  Widget _buildSelectedStockCard(NumberFormat fmt) {
    final s = _selectedStock!;
    final changeColor = s.change >= 0 ? AppColors.green : AppColors.red;
    final changeBg = s.change >= 0 ? AppColors.greenSurface : AppColors.redSurface;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
            color: AppTheme.scoreColor(s.score).withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          ScoreRing(score: s.score, size: 48),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      s.symbol,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    DirectionBadge(direction: s.direction),
                  ],
                ),
                Text(
                  s.name,
                  style: const TextStyle(
                      fontSize: 11, color: AppColors.textMuted),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '₹${fmt.format(s.price)}',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: changeBg,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '${s.change >= 0 ? '+' : ''}${s.change.toStringAsFixed(2)}%',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: changeColor,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPositionRow(Position pos, NumberFormat fmt) {
    final pnlColor = pos.isProfitable ? AppColors.green : AppColors.red;
    final pnlSign = pos.pnl >= 0 ? '+' : '';
    final avatarColor = AppTheme.avatarColor(pos.symbol);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border, width: 0.5),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: avatarColor.withValues(alpha: 0.18),
            ),
            alignment: Alignment.center,
            child: Text(
              pos.symbol.substring(0, pos.symbol.length.clamp(0, 2)),
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: avatarColor,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  pos.symbol,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
                Text(
                  '${pos.qty} shares @ ₹${fmt.format(pos.avgPrice)}',
                  style: const TextStyle(
                      fontSize: 11, color: AppColors.textMuted),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '₹${fmt.format(pos.currentValue)}',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              Text(
                '$pnlSign₹${fmt.format(pos.pnl.abs())} ($pnlSign${pos.pnlPct.toStringAsFixed(1)}%)',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: pnlColor,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryTab(List<Trade> trades, NumberFormat fmt) {
    if (trades.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.history, color: AppColors.textMuted, size: 44),
            SizedBox(height: 16),
            Text(
              'No trades yet',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 15,
                fontWeight: FontWeight.w500,
              ),
            ),
            SizedBox(height: 6),
            Text(
              'Your trade history will appear here',
              style: TextStyle(color: AppColors.textMuted, fontSize: 12),
            ),
          ],
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
      itemCount: trades.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, i) {
        final trade = trades[i];
        final isBuy = trade.isBuy;
        final tradeColor = isBuy ? AppColors.green : AppColors.red;
        final tradeBg = isBuy ? AppColors.greenSurface : AppColors.redSurface;
        final dateStr =
            DateFormat('dd MMM, HH:mm').format(trade.timestamp);

        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.border, width: 0.5),
          ),
          child: Row(
            children: [
              // Timeline dot
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: tradeBg,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(
                  isBuy ? Icons.arrow_downward : Icons.arrow_upward,
                  color: tradeColor,
                  size: 16,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          trade.symbol,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: tradeBg,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            isBuy ? 'BUY' : 'SELL',
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w700,
                              color: tradeColor,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${trade.qty} shares · ₹${fmt.format(trade.price)} · $dateStr',
                      style: const TextStyle(
                          fontSize: 11, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '₹${fmt.format(trade.total)}',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  if (trade.pnl != null)
                    Text(
                      '${trade.pnl! >= 0 ? '+' : ''}₹${fmt.format(trade.pnl!.abs())}',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: trade.pnl! >= 0
                            ? AppColors.green
                            : AppColors.red,
                      ),
                    ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  String _formatLakh(double value) {
    if (value >= 10000000) {
      return '${(value / 10000000).toStringAsFixed(2)}Cr';
    }
    if (value >= 100000) return '${(value / 100000).toStringAsFixed(2)}L';
    if (value >= 1000) return '${(value / 1000).toStringAsFixed(1)}K';
    return value.toStringAsFixed(0);
  }
}
