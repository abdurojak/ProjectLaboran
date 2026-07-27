import 'dart:math' as math;

import 'package:flutter/material.dart';

class LabHubLoading extends StatefulWidget {
  const LabHubLoading({
    super.key,
    this.label = 'Memuat data...',
    this.compact = false,
  });

  final String label;
  final bool compact;

  @override
  State<LabHubLoading> createState() => _LabHubLoadingState();
}

class _LabHubLoadingState extends State<LabHubLoading>
    with SingleTickerProviderStateMixin {
  late final AnimationController controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1350),
  )..repeat();

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final size = widget.compact ? 38.0 : 58.0;
    return Semantics(
      liveRegion: true,
      label: widget.label,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: controller,
            builder: (context, child) => Transform.rotate(
              angle: controller.value * math.pi * 2,
              child: Container(
                width: size,
                height: size,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: colors.primary.withValues(alpha: .28),
                    width: 4,
                  ),
                  gradient: SweepGradient(
                    colors: [
                      colors.primary,
                      colors.primary.withValues(alpha: .08),
                    ],
                  ),
                ),
                padding: const EdgeInsets.all(5),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: colors.surface,
                  ),
                  child: Icon(
                    Icons.science_outlined,
                    color: colors.primary,
                    size: widget.compact ? 20 : 29,
                  ),
                ),
              ),
            ),
          ),
          if (!widget.compact) ...[
            const SizedBox(height: 13),
            Text(
              widget.label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: colors.onSurfaceVariant,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
