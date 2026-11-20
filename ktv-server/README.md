# KTV Server

Servidor local independente para conectar o aplicativo **KTV Orsay** da Samsung Smart TV ao computador. Este módulo é separado do KTV OS e não altera os arquivos do aplicativo instalado na TV.

**Versão inicial: 0.1.0**

## Requisitos

- Windows 10/11, Linux ou macOS
- Python 3.9 ou superior
- Computador e TV na mesma rede local

Não exige pacotes Python externos.

## Iniciar no Windows

Execute `start_server.bat` ou:

```powershell
py server.py
```

Por padrão, o servidor usa a porta TCP 8787. O terminal mostra o endereço para configurar no pacote KTV da TV, o endereço do painel e um token administrativo. Mantenha o terminal aberto durante o uso.

Se precisar informar manualmente o IP do computador:

```powershell
py server.py --ip 192.168.1.20 --port 8787
```

Abra o painel em `http://IP-DO-PC:8787/admin/`. Cole no painel o token exibido no terminal. Libere Python/porta 8787 no Firewall do Windows apenas para redes privadas.

## Integração com o KTV Orsay

O servidor mantém compatibilidade com as rotas consumidas pelo cliente atual:

- `GET /api/health`
- `GET /api/state?client=orsay`
- `GET /api/event?client=orsay&event=...`
- `GET /api/status` (autenticado)
- `GET /media/NOME` com suporte a HTTP Range para busca em vídeos
- `POST /api/admin/upload` (autenticado)
- `POST /api/admin/state` (autenticado)
- `POST /api/admin/command` (autenticado)

O endereço base do servidor precisa ser configurado no arquivo de runtime do pacote da TV. O cliente Orsay continua separado e não é alterado por este módulo.

## Segurança

- O token administrativo é gerado a cada inicialização e exibido apenas no terminal.
- Uploads são limitados a 100 MB e extensões permitidas.
- Não exponha a porta do servidor diretamente à Internet. Use somente em uma rede local confiável.

## Estado desta versão

Esta é a primeira separação do servidor em uma pasta própria. Inclui API compatível com o cliente Orsay, painel web inicial, armazenamento local, upload de mídia, fila de reprodução, telemetria de clientes e suporte a HTTP Range. A integração de ponta a ponta com a TV ainda precisa ser validada após configurar o endereço do novo servidor.
