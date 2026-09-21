import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';

class AuthenticatedNetworkImage extends StatefulWidget {
  const AuthenticatedNetworkImage(
    this.url, {
    super.key,
    this.fit,
    this.width,
    this.height,
    this.errorBuilder,
  });

  final String url;
  final BoxFit? fit;
  final double? width;
  final double? height;
  final ImageErrorWidgetBuilder? errorBuilder;

  @override
  State<AuthenticatedNetworkImage> createState() =>
      _AuthenticatedNetworkImageState();
}

class _AuthenticatedNetworkImageState extends State<AuthenticatedNetworkImage> {
  late Future<Map<String, String>> _headers;

  @override
  void initState() {
    super.initState();
    _headers = context.read<ApiService>().authenticatedMediaHeaders();
  }

  @override
  void didUpdateWidget(covariant AuthenticatedNetworkImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url) {
      _headers = context.read<ApiService>().authenticatedMediaHeaders();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, String>>(
      future: _headers,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return SizedBox(
            width: widget.width,
            height: widget.height,
            child: const Center(child: CircularProgressIndicator()),
          );
        }
        return Image.network(
          widget.url,
          headers: snapshot.data,
          fit: widget.fit,
          width: widget.width,
          height: widget.height,
          errorBuilder: widget.errorBuilder,
        );
      },
    );
  }
}

class AuthenticatedCircleAvatar extends StatefulWidget {
  const AuthenticatedCircleAvatar({
    super.key,
    required this.imageUrl,
    required this.fallback,
    this.radius,
    this.backgroundColor,
  });

  final String? imageUrl;
  final Widget fallback;
  final double? radius;
  final Color? backgroundColor;

  @override
  State<AuthenticatedCircleAvatar> createState() =>
      _AuthenticatedCircleAvatarState();
}

class _AuthenticatedCircleAvatarState extends State<AuthenticatedCircleAvatar> {
  Future<Map<String, String>>? _headers;

  @override
  void initState() {
    super.initState();
    _loadHeaders();
  }

  @override
  void didUpdateWidget(covariant AuthenticatedCircleAvatar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.imageUrl != widget.imageUrl) _loadHeaders();
  }

  void _loadHeaders() {
    _headers = widget.imageUrl == null
        ? null
        : context.read<ApiService>().authenticatedMediaHeaders();
  }

  @override
  Widget build(BuildContext context) {
    final headers = _headers;
    if (headers == null) return _avatar();
    return FutureBuilder<Map<String, String>>(
      future: headers,
      builder: (context, snapshot) => _avatar(snapshot.data),
    );
  }

  Widget _avatar([Map<String, String>? headers]) {
    final ready = headers != null && widget.imageUrl != null;
    return CircleAvatar(
      radius: widget.radius,
      backgroundColor: widget.backgroundColor,
      backgroundImage: ready
          ? NetworkImage(widget.imageUrl!, headers: headers)
          : null,
      child: ready ? null : widget.fallback,
    );
  }
}
