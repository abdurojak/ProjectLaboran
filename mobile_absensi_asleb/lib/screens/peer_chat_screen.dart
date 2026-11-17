import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../services/api_exception.dart';

class PeerChatScreen extends StatefulWidget {
  const PeerChatScreen({super.key});

  @override
  State<PeerChatScreen> createState() => _PeerChatScreenState();
}

class _PeerChatScreenState extends State<PeerChatScreen> {
  final search = TextEditingController();
  Timer? refreshTimer;
  List<Map<String, dynamic>> users = [];
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
    refreshTimer = Timer.periodic(const Duration(seconds: 8), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    search.dispose();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    if (silent && WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) return;
    try {
      final result = await context.read<AttendanceProvider>().api.peerChatUsers();
      if (!mounted) return;
      setState(() {
        users = (result['results'] as List? ?? const [])
            .map((item) => Map<String, dynamic>.from(item as Map)).toList();
        error = null;
        loading = false;
      });
    } on ApiException catch (exception) {
      if (mounted && !silent) setState(() { error = exception.message; loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final query = search.text.toLowerCase().trim();
    final filtered = users.where((user) =>
        (user['name'] as String? ?? '').toLowerCase().contains(query)).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Chat Pengguna')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            controller: search,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search), labelText: 'Cari pengguna',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        if (error != null) Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        ),
        Expanded(child: loading
          ? const Center(child: CircularProgressIndicator())
          : filtered.isEmpty
          ? const Center(child: Text('Pengguna tidak ditemukan.'))
          : ListView.separated(
              itemCount: filtered.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final user = filtered[index];
                final online = user['online'] == true;
                final unread = user['unread_count'] as int? ?? 0;
                return ListTile(
                  leading: CircleAvatar(child: Text((user['name'] as String? ?? '').isEmpty ? '?' : (user['name'] as String)[0].toUpperCase())),
                  title: Text(user['name'] as String? ?? ''),
                  subtitle: Text(online ? 'Aktif di LabHub' : (user['role'] as String? ?? '')),
                  trailing: unread > 0 ? Badge(label: Text('$unread')) : Icon(Icons.circle, size: 10, color: online ? Colors.green : Colors.grey),
                  onTap: () async {
                    await Navigator.push(context, MaterialPageRoute(
                      builder: (_) => PeerChatThreadScreen(userId: user['id'] as int, name: user['name'] as String? ?? ''),
                    ));
                    if (mounted) _load();
                  },
                );
              },
            )),
      ]),
    );
  }
}

class PeerChatThreadScreen extends StatefulWidget {
  const PeerChatThreadScreen({required this.userId, required this.name, super.key});
  final int userId;
  final String name;

  @override
  State<PeerChatThreadScreen> createState() => _PeerChatThreadScreenState();
}

class _PeerChatThreadScreenState extends State<PeerChatThreadScreen> {
  final input = TextEditingController();
  final scroll = ScrollController();
  Timer? refreshTimer;
  List<Map<String, dynamic>> messages = [];
  bool loading = true;
  bool sending = false;
  bool hasMore = false;
  bool loadingOlder = false;
  String? error;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
    refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    input.dispose();
    scroll.dispose();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    if (sending) return;
    if (silent && WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) return;
    try {
      final result = await context.read<AttendanceProvider>().api.peerChatThread(widget.userId);
      if (!mounted) return;
      final incoming = (result['messages'] as List? ?? const [])
          .map((item) => Map<String, dynamic>.from(item as Map)).toList();
      final changed = incoming.isNotEmpty && (messages.isEmpty || incoming.last['id'] != messages.last['id']);
      final merged = <int, Map<String, dynamic>>{
        for (final item in messages) item['id'] as int: item,
        for (final item in incoming) item['id'] as int: item,
      }.values.toList()..sort((a, b) => (a['id'] as int).compareTo(b['id'] as int));
      setState(() {
        if (messages.isEmpty) hasMore = result['has_more'] == true;
        messages = merged;
        loading = false;
        error = null;
      });
      if (changed) WidgetsBinding.instance.addPostFrameCallback((_) {
        if (scroll.hasClients) scroll.jumpTo(scroll.position.maxScrollExtent);
      });
    } on ApiException catch (exception) {
      if (mounted && !silent) setState(() { error = exception.message; loading = false; });
    }
  }

  Future<void> _loadOlder() async {
    if (loadingOlder || messages.isEmpty) return;
    setState(() => loadingOlder = true);
    try {
      final before = messages.first['id'] as int;
      final result = await context.read<AttendanceProvider>().api.peerChatThread(widget.userId, before: before);
      if (!mounted) return;
      final older = (result['messages'] as List? ?? const [])
          .map((item) => Map<String, dynamic>.from(item as Map)).toList();
      setState(() {
        messages = [...older, ...messages];
        hasMore = result['has_more'] == true;
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => loadingOlder = false);
    }
  }

  Future<void> _send() async {
    final text = input.text.trim();
    if (text.isEmpty || sending) return;
    setState(() { sending = true; error = null; });
    try {
      await context.read<AttendanceProvider>().api.sendPeerChatMessage(widget.userId, text);
      input.clear();
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) {
        setState(() => sending = false);
        _load();
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.name)),
    body: Column(children: [
      if (error != null) Padding(
        padding: const EdgeInsets.all(12),
        child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      ),
      Expanded(child: loading
        ? const Center(child: CircularProgressIndicator())
        : ListView.builder(
            controller: scroll,
            padding: const EdgeInsets.all(16),
            itemCount: messages.length + (hasMore ? 1 : 0),
            itemBuilder: (context, index) {
              if (hasMore && index == 0) {
                return Center(child: TextButton(
                  onPressed: loadingOlder ? null : _loadOlder,
                  child: Text(loadingOlder ? 'Memuat...' : 'Muat pesan lama'),
                ));
              }
              final message = messages[index - (hasMore ? 1 : 0)];
              final mine = message['mine'] == true;
              return Align(
                alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * .8),
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: mine ? Theme.of(context).colorScheme.primaryContainer : Theme.of(context).colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(message['text'] as String? ?? ''),
                ),
              );
            },
          )),
      SafeArea(child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Expanded(child: TextField(
            controller: input, maxLines: 3, minLines: 1, maxLength: 2000,
            decoration: const InputDecoration(hintText: 'Tulis pesan', border: OutlineInputBorder()),
          )),
          const SizedBox(width: 8),
          IconButton.filled(
            tooltip: 'Kirim pesan', onPressed: sending ? null : _send,
            icon: const Icon(Icons.send),
          ),
        ]),
      )),
    ]),
  );
}
