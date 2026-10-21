import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/theme.dart';
import 'catalog_screen.dart';
import 'recognize_screen.dart';

class Shell extends StatefulWidget {
  const Shell({super.key, required this.state});

  final AppState state;

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _index = 0;

  Future<void> _editUrl() async {
    final controller = TextEditingController(text: widget.state.api.baseUrl);
    final url = await showDialog<String>(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: Padding(
            padding: const EdgeInsets.all(26),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Endereço do backend',
                    style:
                        TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                const Text(
                    'Por padrão o backend roda em http://127.0.0.1:8000.',
                    style: TextStyle(color: kMuted)),
                const SizedBox(height: 18),
                TextField(
                  controller: controller,
                  autofocus: true,
                  decoration: const InputDecoration(labelText: 'URL base'),
                  onSubmitted: (v) => Navigator.of(context).pop(v),
                ),
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('Cancelar'),
                    ),
                    const SizedBox(width: 12),
                    FilledButton(
                      onPressed: () =>
                          Navigator.of(context).pop(controller.text),
                      child: const Text('Salvar'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (url != null && url.trim().isNotEmpty) {
      await widget.state.setBaseUrl(url);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = IndexedStack(
      index: _index,
      children: [
        RecognizeScreen(state: widget.state),
        CatalogScreen(state: widget.state),
      ],
    );

    return LayoutBuilder(builder: (context, constraints) {
      final compact = constraints.maxWidth < 820;
      if (compact) {
        return Scaffold(
          body: SafeArea(child: pages),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: const [
              NavigationDestination(
                  icon: Icon(Icons.center_focus_strong_outlined),
                  label: 'Identificar'),
              NavigationDestination(
                  icon: Icon(Icons.inventory_2_outlined), label: 'Catálogo'),
            ],
          ),
        );
      }
      return Scaffold(
        body: Row(
          children: [
            _sidebar(),
            Expanded(child: pages),
          ],
        ),
      );
    });
  }

  Widget _sidebar() {
    return Container(
      width: 264,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(right: BorderSide(color: kBorder)),
      ),
      padding: const EdgeInsets.fromLTRB(18, 28, 18, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 46,
                height: 46,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [kGreen, kGreenDark],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: const Text('🍎', style: TextStyle(fontSize: 24)),
              ),
              const SizedBox(width: 12),
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('HortiScan',
                      style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.3)),
                  Text('Identificação no caixa',
                      style: TextStyle(color: kMuted, fontSize: 12.5)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 34),
          _navItem(0, Icons.center_focus_strong_rounded, 'Identificar fruta'),
          const SizedBox(height: 6),
          _navItem(1, Icons.inventory_2_rounded, 'Catálogo'),
          const Spacer(),
          ListenableBuilder(
              listenable: widget.state, builder: (context, _) => _status()),
        ],
      ),
    );
  }

  Widget _navItem(int i, IconData icon, String label) {
    final selected = _index == i;
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () => setState(() => _index = i),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        decoration: BoxDecoration(
          color: selected ? kGreenSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Icon(icon, size: 22, color: selected ? kGreenDark : kMuted),
            const SizedBox(width: 12),
            Text(label,
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: selected ? kGreenDark : kInk,
                )),
          ],
        ),
      ),
    );
  }

  Widget _status() {
    final s = widget.state;
    final Color color = s.checking ? kOrange : (s.online ? kGreen : kRed);
    final String text = s.checking
        ? 'Conectando…'
        : (s.online ? 'Backend online' : 'Backend offline');
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: _editUrl,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: kBg,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(text,
                      style: const TextStyle(
                          fontWeight: FontWeight.w700, fontSize: 13.5)),
                  Text(s.api.baseUrl,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: kMuted, fontSize: 11.5)),
                ],
              ),
            ),
            const Icon(Icons.settings_outlined, size: 18, color: kMuted),
          ],
        ),
      ),
    );
  }
}
