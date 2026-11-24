# KTV Mobile — Android

Primeiro protótipo Android independente do KTV OS desktop.

## Build local
Requisitos: JDK 17, Android SDK (platform 35) e Gradle 8.9.\n
```bash
cd ktv-mobile
gradle assembleDebug
```
APK: `app/build/outputs/apk/debug/app-debug.apk`

## Build automático
O workflow `.github/workflows/build-ktv-mobile.yml` gera APK Debug:
- push/PR com alterações em `ktv-mobile/**`;
- execução manual em Actions → Build KTV Mobile APK → Run workflow.
Baixe o artefato `KTV-Mobile-debug-<run>` no fim da execução.

## Estado atual (0.1.0)
- Home Jetpack Compose com tema escuro;
- navegação Início / Favoritos / Ajustes;
- busca visual e categorias iniciais;
- tela preparatória de conexão com TV.

Ainda não implementados: playlist IPTV real, player, favoritos persistentes, Chromecast/DLNA e espelhamento.
