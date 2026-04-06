import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class DirectionBadge extends StatelessWidget {
  final String direction;
  final double fontSize;
  final EdgeInsets? padding;

  const DirectionBadge({
    super.key,
    required this.direction,
    this.fontSize = 9,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.directionColor(direction);
    final label = direction.toUpperCase();

    return Container(
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.4), width: 0.5),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: fontSize,
          fontWeight: FontWeight.w700,
          color: color,
          letterSpacing: 0.4,
        ),
      ),
    );
  }
}
