# Agenda Sem Fricção — piloto individual

Esta pasta contém uma instância individual pronta para publicação: login obrigatório, senha com PBKDF2, dados persistidos em PostgreSQL, agenda, retornos, sala e notificações por e-mail.

## Rodar localmente

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Sem variáveis de ambiente, o modo local usa SQLite e dados demonstrativos. O modo de produção deve sempre definir `AGENDA_AUTH_REQUIRED=1`, `AGENDA_SEED_DEMO=0` e `DATABASE_URL`.

## Criar o login do vendedor

Execute sem colocar a senha na linha de comando:

```bash
python create_user.py --username vendedor --name "Nome do vendedor"
```

O comando pedirá uma senha de pelo menos 12 caracteres e imprimirá apenas o hash e os segredos necessários. Guarde essas variáveis no ambiente da hospedagem; não crie um arquivo `.env` versionado.

## Publicar no Railway

1. Versione esta pasta em um repositório privado no GitHub, ou configure `agenda_piloto` como **Root Directory** no projeto existente.
2. No Railway, crie um projeto a partir do repositório e adicione um serviço PostgreSQL.
3. Confirme que `DATABASE_URL` do PostgreSQL está disponível no serviço da agenda.
4. Adicione as variáveis geradas por `create_user.py` e mantenha `AGENDA_ROLE=seller`.
5. Configure as variáveis SMTP do `.env.example` para que os lembretes cheguem por e-mail.
6. Gere um domínio público, abra `/_stcore/health` para conferir a saúde e depois teste o login no endereço principal.

O `Dockerfile` respeita a porta fornecida pela hospedagem. O estado fica no PostgreSQL, portanto reiniciar ou atualizar o contêiner não apaga a agenda.

## Checklist antes de entregar

- Login incorreto não entra; login correto abre somente “Minha agenda”.
- Criar um retorno, atualizar a página e confirmar que ele continua salvo.
- Testar “Feito”, “Sem resposta”, “Remarcar” e “Desfazer”.
- Criar reunião com sala e validar que conflito de sala é bloqueado.
- Enviar uma notificação de teste e confirmar o recebimento.
- Manter apenas uma réplica do serviço durante o piloto.

## Escopo conhecido do piloto

O componente visual `streamlit-calendar` usa licença Apache-2.0. Esta versão foi preparada para uma única pessoa e uma única réplica do serviço; autenticação multiusuário, trilha de auditoria e administração de contas pertencem à próxima etapa. O histórico do gestor existe no produto, mas fica oculto quando `AGENDA_ROLE=seller`.
