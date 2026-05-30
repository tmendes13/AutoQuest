# Memory Keeper — Mecanismo de Compressão e Otimização de Memória

Este documento relata detalhadamente o funcionamento, a lógica de engenharia de prompts e a implementação física das técnicas de compressão de contexto e otimização de memória aplicadas ao **Memory Keeper** e ao gerenciamento do arquivo de fatos do Game Master nesta iteração.

---

## 1. O Problema do Crescimento Exponencial de Contexto no GM

Num simulador síncrono baseado em agentes de linguagem (LLMs) executando múltiplas rodadas:
1. **Histórico Acumulado**: Cada narração do GM e ação síncrona deliberada da party acrescenta dezenas de linhas e centenas de tokens ao contexto narrativo global.
2. **Poluição de Raciocínio (Chat Pollution)**: Manter chats com histórico ativo (`remember=True`) nos sub-agentes do GM (Narrador, Arbiter e Memory Keeper) faz com que as LLMs processem rascunhos intermédios obsoletos, decisões de formatação rígidas antigas e prosa descartável. Isto provoca crescimento exponencial no contexto e degradação progressiva da qualidade lógica (alucinação).

A solução nesta iteração aborda estes dois eixos estruturais de compressão focados na arquitetura do Game Master.

---

## 2. Como Funciona a Compressão da Memória do Game Master

A compressão da memória baseia-se num modelo híbrido de **Memória Curta vs. Memória Longa** auxiliado por **Extração Seletiva de Fatos**:

### 2.1. Sentinela `NO_RELEVANT_FACTS`

Antes da compressão, o Memory Keeper deve ser seletivo sobre o que realmente afeta a consistência futura do jogo:
* **Fatos Duráveis**: Apenas mudanças de localização física, presença de inimigos ou NPCs chave, inventário consolidado e descobertas fundamentais são salvos.
* **Sentinela**: Se o texto avaliado não contiver fatos duráveis para o futuro, a LLM responde estritamente `NO_RELEVANT_FACTS`. A função `mem_keep()` devolve `None` e nenhuma escrita redundante ou poluente é feita na memória global.

### 2.2. Condensação Periódica de Fatos Globais

O Memory Keeper monitoriza e condensa de forma síncrona o número de fatos validados no ficheiro principal `memory/memory.json`:

* **Gatilho de Condensação**: Após `CONDENSE_AFTER_VALIDATED_ENTRIES = 10` novas entradas validadas.
* **Memória Curta (Local Context)**: As `RECENT_VALIDATED_ENTRIES_TO_KEEP = 4` entradas validadas mais recentes são mantidas intactas e separadas. Isso preserva a continuidade imediata e o contexto de curto prazo sem perda de precisão local.
* **Memória Longa (Global Summary)**: Todas as entradas anteriores validadas mais antigas são enviadas ao Memory Keeper com uma prompt especializada de reescrita. A LLM condensa todos os fatos históricos obsoletos, removendo redundâncias, contradições e eventos temporários já resolvidos, gravando um snapshot único de consolidação com `kind="summary"`.

---

## 3. Como Foi Feita a Implementação

A arquitetura de compressão e otimização de dados do Game Master foi implementada através das seguintes camadas integradas:

### 3.1. Chamadas Stateless nos Agentes (`remember=False`)

Refatorámos o wrapper síncrono `_Chat.send_message` em [config.py](file:///c:/Users/Luisr/Desktop/IST/ASSMA/AutoQuest/config.py) para suportar chamadas stateless:

```python
response = send_chat_message(chat, context, remember=False)
```

> [!NOTE]
> Quando `remember=False` é ativado, o histórico interno de mensagens do chat (`chat.messages`) é ignorado e mantido limpo. A LLM do Narrador, Arbiter e Memory Keeper responde baseando-se única e exclusivamente no estado da memória validada consolidada que lhe é injetada de forma limpa no prompt a cada turno, neutralizando totalmente o acúmulo de contexto residual nos chats e mantendo a compressão ativa.

### 3.2. Histórico Bruto Não Comprimido para Comparação

Para auditar a fidelidade e eficácia da compressão narrativa do Memory Keeper, implementámos uma gravação duplicada física em tempo real no módulo [memory_store.py](file:///c:/Users/Luisr/Desktop/IST/ASSMA/AutoQuest/agents/gm/memory_store.py):

```python
def _append_to_uncompressed(path: str, entry: dict) -> None:
    # Grava a cópia exata do fato validado no ficheiro memory_uncompressed.json
```

Desta forma, enquanto o motor de jogo lê a memória otimizada e comprimida para economizar tokens, o utilizador pode abrir `memory/memory_uncompressed.json` para auditar a história completa e linear sem qualquer perda do histórico original de fatos, servindo de contraprova para o algoritmo de condensação.

---

## 4. Diferenças e Melhorias Implementadas

A tabela abaixo resume as melhorias e evoluções aplicadas ao sistema de memória do Game Master nesta iteração em comparação com a estrutura anterior:

| Funcionalidade | Estado Anterior | Estado Atual (Melhorado) | Benefício Técnico |
| :--- | :--- | :--- | :--- |
| **Mecanismo de Comunicação** | Stateful (acumulava rascunhos antigos nos chats do GM). | 100% Stateless com injeção limpa de fatos validados. | **Zero Poluição**: Impede crescimento linear no contexto interno dos sub-agentes do GM. |
| **Organização Física** | Espalhada na raiz do projeto. | Unificada e encapsulada na pasta física `memory/`. | **Higienização**: Facilita a auditoria de logs e isola o estado do motor de simulação. |
| **Auditoria Narrativa** | Apenas memória comprimida em disco. | Gravação duplicada física e unificada em `memory/memory_uncompressed.json`. | **Transparência**: Permite ao desenvolvedor comparar a fidelidade da condensação em tempo real. |

---

## 5. Validação Prática

O sistema de compressão do Memory Keeper foi validado e testado com absoluto sucesso:
1. **Testes Unitários**: A suite [test_memory_management.py](file:///c:/Users/Luisr/Desktop/IST/ASSMA/AutoQuest/tests/test_memory_management.py) comprovou que a condensação substitui entradas antigas preservando as mais recentes, entradas não validadas ficam protegidas e `NO_RELEVANT_FACTS` bloqueia escritas redundantes.
2. **Execução Real**: Confirmada a criação física e atualização do arquivo de fatos comprimido na pasta `memory/` provando estabilidade matemática no consumo de contexto ao longo do tempo.
