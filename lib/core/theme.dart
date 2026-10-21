import 'package:flutter/material.dart';

const kGreen = Color(0xFF2E7D4F);
const kGreenDark = Color(0xFF1E5C38);
const kGreenSoft = Color(0xFFE3F1E8);
const kOrange = Color(0xFFE67E22);
const kOrangeSoft = Color(0xFFFFEFDB);
const kRed = Color(0xFFD64545);
const kRedSoft = Color(0xFFFCE7E7);
const kBlue = Color(0xFF2F6FDE);
const kBlueSoft = Color(0xFFE5EEFD);
const kBg = Color(0xFFF4F6F0);
const kInk = Color(0xFF1B2A22);
const kMuted = Color(0xFF6B7A70);
const kBorder = Color(0xFFE2E6DC);

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: kGreen, brightness: Brightness.light)
      .copyWith(primary: kGreen, secondary: kOrange);

  OutlineInputBorder border(Color color, [double width = 1]) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: color, width: width),
      );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: kBg,
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: border(kBorder),
      enabledBorder: border(kBorder),
      focusedBorder: border(kGreen, 1.8),
      errorBorder: border(kRed),
      focusedErrorBorder: border(kRed, 1.8),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 50),
        padding: const EdgeInsets.symmetric(horizontal: 22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 50),
        padding: const EdgeInsets.symmetric(horizontal: 22),
        foregroundColor: kInk,
        side: const BorderSide(color: kBorder),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: kGreen,
        textStyle: const TextStyle(fontWeight: FontWeight.w600),
      ),
    ),
  );
}
