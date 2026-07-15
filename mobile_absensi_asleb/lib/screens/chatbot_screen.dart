import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../services/api_exception.dart';
import '../utils/app_theme.dart';

class ChatbotScreen extends StatefulWidget {
  const ChatbotScreen({super.key});

  @override
  State<ChatbotScreen> createState() => _ChatbotScreenState();
}

class _ChatbotScreenState extends State<ChatbotScreen> {
  final controller = TextEditingController();
  final messages = <_ChatMessage>[];
  bool sending = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final profile = context.read<AttendanceProvider>().profile;
      setState(() {
        messages
          ..clear()
          ..add(
            _ChatMessage(
              fromBot: true,
              text:
                  'Halo ${profile?.nama ?? 'Asisten Lab'}, saya Bot Bantuan LabHub. Mau tanya jadwal, absensi, honor, atau kendala aplikasi?',
            ),
          );
      });
    });
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> sendMessage() async {
    final text = controller.text.trim();
    if (text.isEmpty || sending) return;
    setState(() {
      messages.add(_ChatMessage(fromBot: false, text: text));
      sending = true;
      controller.clear();
    });
    try {
      final answer = await context.read<AttendanceProvider>().api.askChatbot(
        text,
      );
      if (!mounted) return;
      setState(() => messages.add(_ChatMessage(fromBot: true, text: answer)));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(
        () => messages.add(
          _ChatMessage(
            fromBot: true,
            text: 'Maaf, bot belum bisa menjawab. ${error.message}',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Chat Bantuan')),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
              itemCount: messages.length + (sending ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == messages.length) {
                  return const _MessageBubble(
                    message: _ChatMessage(
                      fromBot: true,
                      text: 'Bot sedang mengetik...',
                    ),
                  );
                }
                return _MessageBubble(message: messages[index]);
              },
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
                      onSubmitted: (_) => sendMessage(),
                      decoration: const InputDecoration(
                        hintText: 'Tulis pertanyaan...',
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  FilledButton(
                    onPressed: sending ? null : sendMessage,
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(54, 54),
                      padding: EdgeInsets.zero,
                    ),
                    child: const Icon(Icons.send_rounded),
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

class _ChatMessage {
  const _ChatMessage({required this.fromBot, required this.text});
  final bool fromBot;
  final String text;
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});
  final _ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final alignment = message.fromBot
        ? CrossAxisAlignment.start
        : CrossAxisAlignment.end;
    final color = message.fromBot ? Colors.white : AppTheme.teal;
    final textColor = message.fromBot ? AppTheme.navy : Colors.white;
    return Column(
      crossAxisAlignment: alignment,
      children: [
        Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * .78,
          ),
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(18),
            border: message.fromBot
                ? Border.all(color: const Color(0xFFDDE8E8))
                : null,
          ),
          child: Text(
            message.text,
            style: TextStyle(
              color: textColor,
              height: 1.4,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}
