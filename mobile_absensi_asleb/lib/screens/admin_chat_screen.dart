import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../services/api_exception.dart';
import '../widgets/labhub_loading.dart';

class AdminChatScreen extends StatefulWidget {
  const AdminChatScreen({super.key});

  @override
  State<AdminChatScreen> createState() => _AdminChatScreenState();
}

class _AdminChatScreenState extends State<AdminChatScreen> {
  final controller = TextEditingController();
  final scrollController = ScrollController();
  List<Map<String, dynamic>> messages = [];
  String status = 'bot';
  bool loading = true;
  bool sending = false;
  String? error;
  Timer? refreshTimer;

  @override
  void initState() {
    super.initState();
    Future.microtask(_openConversation);
    refreshTimer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _load(silent: true),
    );
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    controller.dispose();
    scrollController.dispose();
    super.dispose();
  }

  Future<void> _openConversation() async {
    try {
      final api = context.read<AttendanceProvider>().api;
      var data = await api.adminChat();
      if (data['status'] == 'bot') data = await api.startAdminChat();
      _apply(data);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _load({bool silent = false}) async {
    if (!mounted || sending) return;
    if (!silent) setState(() => loading = true);
    try {
      final data = await context.read<AttendanceProvider>().api.adminChat();
      _apply(data);
    } on ApiException catch (exception) {
      if (mounted && !silent) setState(() => error = exception.message);
    } finally {
      if (mounted && !silent) setState(() => loading = false);
    }
  }

  void _apply(Map<String, dynamic> data) {
    if (!mounted) return;
    final incoming = (data['messages'] as List? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    setState(() {
      messages = incoming;
      status = data['status'] as String? ?? 'admin';
      error = null;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (scrollController.hasClients) {
        scrollController.animateTo(
          scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = controller.text.trim();
    if (text.isEmpty || sending) return;
    setState(() {
      sending = true;
      error = null;
    });
    try {
      final data = await context
          .read<AttendanceProvider>()
          .api
          .sendAdminMessage(text);
      controller.clear();
      _apply(data);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Chat Admin',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        actions: [
          IconButton(
            tooltip: 'Muat ulang pesan',
            onPressed: loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: colors.primaryContainer,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.support_agent_rounded,
                  color: colors.onPrimaryContainer,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    status == 'admin'
                        ? 'Percakapan masuk antrean admin. Balasan diperbarui otomatis.'
                        : 'Percakapan bantuan sudah selesai.',
                    style: TextStyle(
                      color: colors.onPrimaryContainer,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Text(error!, style: TextStyle(color: colors.error)),
            ),
          Expanded(
            child: loading && messages.isEmpty
                ? const Center(
                    child: LabHubLoading(label: 'Memuat percakapan...'),
                  )
                : ListView.builder(
                    controller: scrollController,
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 18),
                    itemCount: messages.length,
                    itemBuilder: (context, index) =>
                        _AdminMessageBubble(message: messages[index]),
                  ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: controller,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: const InputDecoration(
                        hintText: 'Tulis pesan untuk admin...',
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  FilledButton(
                    onPressed: sending ? null : _send,
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(54, 54),
                      padding: EdgeInsets.zero,
                    ),
                    child: sending
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send_rounded),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminMessageBubble extends StatelessWidget {
  const _AdminMessageBubble({required this.message});
  final Map<String, dynamic> message;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final isUser = message['sender'] == 'pengguna';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .8,
        ),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
        decoration: BoxDecoration(
          color: isUser ? colors.primary : colors.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(18),
          border: isUser ? null : Border.all(color: colors.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              message['sender_display']?.toString() ??
                  (isUser ? 'Anda' : 'Admin'),
              style: TextStyle(
                color: isUser ? colors.onPrimary : colors.primary,
                fontSize: 11,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              message['text']?.toString() ?? '',
              style: TextStyle(
                color: isUser ? colors.onPrimary : colors.onSurface,
                height: 1.4,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
