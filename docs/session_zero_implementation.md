# Sessão 0 — Criação Dinâmica de Personagens

## Visão Geral

A **Sessão 0** é um protocolo que decorre **antes do início da campanha**. Em vez de usar personagens pré-definidos no código (Thorin e Aelindra), o sistema agora:

1. Pergunta ao utilizador quantos jogadores quer (1 a 6)
2. Cria N agentes com placeholders
3. Executa uma deliberação completa de criação de personagens
4. Valida o resultado com o Árbitro
5. Guarda as fichas como bloco protegido na memória partilhada e no diário privado de cada jogador

Só depois disto é que a campanha começa.

---

## Ficheiros Modificados / Criados

### Novo Ficheiro

| Ficheiro | Descrição |
|----------|-----------|
| `agents/session_zero.py` | Módulo completo do protocolo de Sessão 0 (~460 linhas) |

### Ficheiros Modificados

| Ficheiro | Alterações |
|----------|------------|
| `models/player.py` | Adicionado campo `attributes: dict[str, int]`; `status()` inclui atributos |
| `main.py` | Input dinâmico de N jogadores; chamada a `run_session_zero()` antes de `begin_campaign()` |
| `web/server.py` | Igual ao `main.py` mas com eventos WebSocket; `start_game` aceita `num_players` do frontend |
| `web/templates/index.html` | Input numérico para escolher número de jogadores (1-6) com estilo dourado |
| `agents/gm/memory_store.py` | Bloco protegido `protected_player_data`; `format_validated()` inclui tags `[SYSTEM_PROTECTED_PLAYER_DATA]` |
| `agents/player.py` | Nova função `save_character_sheet_to_diary()` |

---

## Arquitetura do Protocolo

```
┌─────────────────────────────────────────────────┐
│              UTILIZADOR (N jogadores)            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Criar N Players com placeholders               │
│  (Player_1, Player_2, ..., Player_N)            │
│  Raça: "Unknown", Classe: "Unknown", HP: 100    │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  1. NARRADOR — Pitch do Mundo                   │
│  • Apresenta o cenário (Medieval Fantasy)       │
│  • Define o tom (Epic Adventure)                │
│  • Explica o Standard Array                     │
│  • Pede a cada jogador para se apresentar       │
│  • Escrita na memória como validated seed       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  2. JOGADORES — Deliberação de Personagens      │
│                                                 │
│  a) Cada jogador propõe a sua personagem:       │
│     • Nome, Raça, Classe                        │
│     • Standard Array distribuído (6 atributos)  │
│     • Personalidade (1 frase)                   │
│     • Ligação de backstory com o grupo          │
│                                                 │
│  b) Um starter aleatório sintetiza tudo         │
│     numa ficha de grupo unificada               │
│                                                 │
│  c) Circulação: cada jogador revê e decide:     │
│     • APPROVE — aceita a ficha como está        │
│     • MODIFY — propõe alterações (máx 3/player) │
│                                                 │
│  d) O processo repete-se até todos aprovarem    │
│     ou os modificadores esgotarem               │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  3. SPOKESPERSON — Compilação Final             │
│  • Um jogador aleatório compila a decisão       │
│    do grupo num formato estruturado             │
│  • Formato:                                     │
│    Player_N: {Name, Race, Class,                │
│    Attributes: [Str:X, Dex:X, ...],             │
│    HP: 100, Personality: ...}                   │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  4. MEMORY KEEPER — Registo (não validado)      │
│  • Escreve a ficha compilada na memória         │
│  • Estado: validated = false                    │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  5. VALIDAÇÃO PROGRAMÁTICA (PRE-VALIDATION)     │
│  • Feita em Python puro (sem custos de tokens)  │
│  • Garante que:                                 │
│    ✓ Nº de personagens coincide com num_players │
│    ✓ Todos têm os 6 valores do Standard Array   │
│    ✓ Todos começam com HP: 100                  │
│                                                 │
│  • Se inválido → faz retry imediato             │
│  • Se válido → passa para o Árbitro             │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  6. ÁRBITRO — Validação Final                   │
│  • Verifica:                                    │
│    ✓ Consistência temática (Medieval Fantasy)   │
│    ✓ Regras adicionais e consistência do mundo │
│                                                 │
│  • Se VÁLIDO → continua                         │
│  • Se INVÁLIDO → apaga entrada, volta ao passo 2│
│    (máximo 3 tentativas)                        │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  7. FINALIZAÇÃO                                 │
│  • Escreve bloco protegido na memória           │
│  • Atualiza objetos Player (raça, classe, etc.) │
│  • Guarda ficha no campo `character_sheet`      │
│    do diário privado de cada um                 │
│  • Re-configura system prompts dos agentes      │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  begin_campaign() → JOGO NORMAL                 │
└─────────────────────────────────────────────────┘
```

---

## Bloco Protegido na Memória

### Estrutura do ficheiro `memory.json`

```json
{
  "protected_player_data": "Player_1: {Name: Aragorn, Race: Human, ...}\nPlayer_2: {...}",
  "entries": [
    {
      "id": "abc12345",
      "validated": true,
      "author": "narrator",
      "content": "Pitch do mundo...",
      "kind": "event"
    }
  ],
  "metadata": {
    "validated_since_condense": 1
  }
}
```

### Como aparece para os agentes (via `format_validated()`)

```
[SYSTEM_PROTECTED_PLAYER_DATA]
Player_1: {Name: Aragorn, Race: Human, Class: Warrior, Attributes: [Str:15, Dex:12, Con:14, Int:10, Wis:13, Cha:8], HP: 100, Personality: Noble and brave}
Player_2: {Name: Lirael, Race: Elf, Class: Mage, Attributes: [Str:8, Dex:14, Con:12, Int:15, Wis:13, Cha:10], HP: 100, Personality: Curious and mysterious}
[/SYSTEM_PROTECTED_PLAYER_DATA]

--- HISTORICO DE JOGO (COMPRESSIVEL) ---
[validated] [narrator] (id=abc12345): Pitch do mundo...
[validated] [party] (id=def67890): O grupo decide explorar a torre...
```

### Proteção contra compressão

O algoritmo de condensação (`condense_memory`) opera **apenas** sobre o array `entries[]`. O campo `protected_player_data` **nunca** é tocado, truncado ou resumido. Isto garante que:

- As fichas de personagem sobrevivem a **todas** as compressões de memória
- Os atributos, raça, classe e personalidade são **imutáveis** durante a campanha
- O Árbitro pode sempre verificar consistência contra a ficha original

---

## Diários Privados

Cada jogador tem um ficheiro individual: `memory/memory_diary_{Nome}.json`.

Para evitar que as fichas de personagem sejam sobrescritas durante a consolidação de pensamentos (no método `reflect()`), os diários foram reestruturados para separar fisicamente a ficha imutável dos pensamentos dinâmicos:

### Estrutura do ficheiro de diário

```json
{
  "diary": "- Fico de guarda enquanto o núcleo de obsidiana goteja.\n- Bronn está ferido...",
  "character_sheet": "CHARACTER SHEET\nName: Player_1\nRace: Half-Elf\nClass: Ranger\nAttributes: Strength:12, Dexterity:15, Constitution:13...\nHP: 100/100\n"
}
```

- **`character_sheet`**: Contém a ficha de personagem gerada na Sessão 0. É **imutável** e serve de âncora permanente.
- **`diary`**: Contém os pensamentos e reflexões diárias consolidadas pelo método `reflect()`.
- O método `reflect()` agora lê a `character_sheet` para se contextualizar sobre quem é o jogador, mas grava apenas o seu output em `diary`, preservando a ficha intacta ao longo de toda a campanha.

---

## Fluxo no `main.py` (CLI)

```
> python main.py
Enter number of players (1-6): 3

========== SESSION 0: CHARACTER CREATION ==========

[GM-Narrator] Pitching the world...
[GM-Narrator Session 0 pitch]
Welcome, brave adventurers, to the realm of...

--- Session 0: character proposals ---
  [Player_1] proposes: I am Aragorn, a Human Warrior...
  [Player_2] proposes: I am Lirael, an Elf Mage...
  [Player_3] proposes: I am Durin, a Dwarf Cleric...

--- Starter: Player_2 ---
[Player_2 synthesises]: Unified party sheet...

--- Circulation pass 1 ---
  [Player_1] APPROVES
  [Player_3] MODIFIES (remaining 2/3)

--- Circulation pass 2 ---
  [Player_2] APPROVES

[Spokesperson] Compiling final output...
[Spokesperson Player_3]: Structured output...

[Arbiter] VALID: All 3 characters use Standard Array and are thematically consistent.

========== SESSION 0 COMPLETE ==========

[Session 0 Result] Arbiter: VALID
[Session 0] Spokesperson: Player_3

[GM-Narrator opening] The three adventurers meet at the tavern...
```

---

## Fluxo no Frontend Web

1. Utilizador abre `http://127.0.0.1:5050`
2. Vê o ecrã de boas-vindas com:
   - Título "AutoQuest"
   - Input numérico "Number of Players" (1-6, default 2)
   - Botão "Start Campaign"
3. Clica "Start Campaign" → o frontend envia `{num_players: N}` via WebSocket
4. O servidor executa a Sessão 0, emitindo eventos em tempo real:
   - `phase: session_zero` — "Narrator is pitching the world..."
   - `gm_agent` — Pitch do Narrador
   - `gm_agent` — Propostas de cada jogador
   - `gm_agent` — Síntese do starter
   - `gm_agent` — Decisões de APPROVE/MODIFY
   - `gm_agent` — Ficha final
   - `system` — Resultado do Árbitro
5. Após Sessão 0, os cards de jogador aparecem com informação real
6. A campanha começa normalmente

---

## Detalhes Técnicos

### Standard Array

Os 6 valores `[15, 14, 13, 12, 10, 8]` são distribuídos pelos atributos:

| Atributo | Abreviatura |
|----------|-------------|
| Strength | Str |
| Dexterity | Dex |
| Constitution | Con |
| Intelligence | Int |
| Wisdom | Wis |
| Charisma | Cha |

### Constantes de Configuração

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `SESSION_ZERO_MAX_ROUNDS` | 3 | Tentativas máximas de deliberação (com Árbitro) |
| `MAX_MODIFICATIONS` | 3 | Modificações máximas por jogador |
| `NUM_ROUNDS` | 20 | Turnos da campanha (partilhado no CLI e no Servidor Web) |
| `HP inicial` | 100 | HP de todos os personagens |

### Parsing Robusto de Atributos e Info

A função `_parse_player_attributes_from_sheet()` foi reestruturada para ser extremamente tolerante a variações na formatação dos modelos (LLMs). Ela tenta fazer a correspondência usando uma sequência de múltiplas expressões regulares:

```python
patterns = [
    # Formato abreviado [Str:X, Dex:Y...]
    rf'{re.escape(player_name)}.*?Attributes:\s*\[Str:(\d+),\s*Dex:(\d+),\s*Con:(\d+),\s*Int:(\d+),\s*Wis:(\d+),\s*Cha:(\d+)\]',
    # Formato completo [Strength:X, Dexterity:Y...]
    rf'{re.escape(player_name)}.*?Attributes:\s*\[Strength:(\d+),\s*Dexterity:(\d+),\s*Constitution:(\d+),\s*Intelligence:(\d+),\s*Wisdom:(\d+),\s*Charisma:(\d+)\]',
    # Formato sem delimitadores diretos
    rf'{re.escape(player_name)}.*?Str[^:]*[:\s]*(\d+).*?Dex[^:]*[:\s]*(\d+).*?Con[^:]*[:\s]*(\d+).*?Int[^:]*[:\s]*(\d+).*?Wis[^:]*[:\s]*(\d+).*?Cha[^:]*[:\s]*(\d+)',
]
```

Adicionalmente, o parser de info (`_parse_player_info_from_sheet`) limpa delimitadores JSON residuais (como `}`) que os modelos possam injetar no final das linhas de propriedades de texto.

### Fallback e Robustez da Simulação

Em vez de aceitar silenciosamente uma ficha inválida caso as 3 tentativas esgotem (o que corromperia as regras da simulação), o sistema agora:
- **Lança uma exceção `RuntimeError`** detalhando o erro que causou a rejeição.
- O `main.py` e o `web/server.py` capturam este erro, informam o utilizador e abortam a campanha de forma segura, garantindo que nunca corre um jogo com regras violadas.

---

## Unificação do Motor de Jogo (Game Loop DRY)

Anteriormente, o `web/server.py` continha centenas de linhas de lógica duplicada que reimplementavam os turnos e a lógica de retry/validação do `main.py`.

### Nova Abordagem com Callback de Eventos
A lógica foi unificada dentro de `run_turn()` no ficheiro `agents/gm/gm.py`. A função agora aceita um callback opcional `on_event(event_type, data)` que permite ao servidor Web transmitir em tempo real todas as fases do jogo para os WebSockets de forma nativa e sem redundância de código:

```python
# No web/server.py, o game loop resume-se a:
try:
    for round_num in range(NUM_ROUNDS):
        emit_event('round_start', {'round': round_num + 1})
        situation = run_turn(gm, players, situation, on_event=emit_event)
        emit_event('round_end', {'round': round_num + 1})
except GMRetriesExhaustedError as e:
    emit_event('game_over', {'message': 'Campaign Aborted.'})
```

---

## Testes

Os testes existentes continuam a funcionar:

- `tests/test.py` — Teste básico de modelos (Player, Item, Class)
- `tests/test_diary_segregation.py` — Verifica que diários são isolados por jogador
- `tests/test_memory_management.py` — Verifica compressão e validação de memória

Para testar a Sessão 0:

```bash
# CLI
python main.py
# Introduzir número de jogadores e observar o fluxo completo

# Web
python web/server.py
# Abrir http://127.0.0.1:5050, escolher N, clicar Start Campaign
```
