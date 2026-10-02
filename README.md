# btc_finder
A simple script written in python inspired by BTC Puzzle.
 
* The project was inspired by Bitcoin Puzzle.
* The objective of the project is to expand knowledge in the process of generating Bitcoin keys and addresses.

The project that wants the MongoDB version installed:
```
https://www.mongodb.com/try/download/community
```
The BIP39 script was based on the following challenge: (and is configured for the same. The text in question is in the Texto_base.txt file)
```
https://www.youtube.com/watch?v=dhrY0dkNb5c
```

* Installation (The project was developed using Python3-venv):

```
python3 -m pip install -r requirements.txt
```
```
python3 btc_finder.py
```
[![Demonstração de uso]](https://www.youtube.com/watch?v=igaNrEXukRA)

(Qualquer dúvida ou sugestão -> https://discord.gg/VFx3KkAame)

Ajude-nos a continuar o projeto! Próximas implementações:

* Testes automatizados

* Monitor de hardware

Sugestões de implementação (ordem prática)
Corrigir o import e um único caminho de address: compressed por padrão, uncompressed opcional.
Unificar schema: priv_key_hex, address, status, is_verified. Migrar documentos antigos ou mapear os dois nomes na leitura.
Índice único em priv_key_hex; tirar o full-scan de duplicatas do menu.
Um MongoClient com timeout; URI via env (MONGODB_URI), não hardcoded só em localhost.
Worker multiprocessing deve: gerar compressed address → comparar alvo → inserir lote → atualizar progresso. Sem trabalho morto.
Pool: token obrigatório; post_keys com kwargs corretos; enviar batch_check na hora; não varrer a coleção inteira em get_db_priv_keys (query por range).
Progresso: tqdm por chaves realmente processadas; o thread de progresso hoje espera get() para sempre se o último lote for < 1000 (deadlock possível).
hex_to_int e hex_to_decimal são iguais — um só método.
Testes mínimos: round-trip chave conhecida → address compressed conhecido (vetor do puzzle 1 ou uma chave de teste); import da pool; ping Mongo.

4.3 Problemas Identificados
Problema	Descrição	Impacto
Redundância	generate_random_hex já verifica attempted_keys; o if seguinte é redundante.	Baixo
Concorrência em attempted_keys	Sem locks, threads podem adicionar/ler simultaneamente.	Médio
Uso de print em loop	I/O em thread reduz throughput.	Alto em produção
Duplicação de entrada no alvo	Quando encontra o alvo, insere duas entradas (uma not found e uma found).	Lógico
batch_size não utilizado	Definido mas não aplicado no trecho visível.	Incompleto
count não utilizado	Variável declarada mas nunca incrementada/usada.	Código morto
total_iterations não utilizado	Calculado mas não usado no trecho.	Código morto
Ausência de inserção no MongoDB	O trecho termina sem insert_many ou similar.	Incompleto
5. Compatibilidade com Bitcoin Moderno

O trecho fornecido (na tabela do arquivo) indica:

    Sim, dependendo do endereço derivado

Isso está correto: a compatibilidade depende do formato do endereço-alvo e do tipo de chave pública gerada.

    Se o endereço-alvo for P2PKH (prefixo 1), como 1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU, a chave pública pode ser não comprimida ou comprimida — ambos os formatos geram o mesmo endereço P2PKH? Não exatamente: endereços P2PKH são derivados do hash da chave pública. Chaves comprimidas e não comprimidas geram endereços diferentes para a mesma chave privada. Portanto, é crucial usar o formato correto.

    No código, private_key_to_public_key é chamado sem o parâmetro compressed. Isso significa que, se a implementação padrão for a Versão 1 (não comprimida), o endereço gerado será P2PKH não comprimido. Se for a Versão 2 com compressed=True (padrão), será P2PKH comprimido.

    Endereços modernos (SegWit, Taproot) exigiriam lógicas adicionais de derivação (bech32, bech32m), que não aparecem no trecho

    , recomenda-se:

    Remover print do loop interno.

    Usar locks ou estruturas thread-safe para attempted_keys.

    Implementar inserção em lote (insert_many) com batch_size.

    Corrigir a duplicação de entradas ao encontrar o alvo.

    Tornar explícito o formato de compressão da chave pública.


### A intenção de acordo com o apoio é a implementação de uma POOL online de código aberto 

![BTC Wallet](apoio/BTC_address.jpg) BTC ```bc1q6e78uszvaahp2zdn67na2hyl5ycl9kfsmurmtk```

![Solana Wallet](apoio/Solana_address.jpg) Solana ```J7z6qmPsJXMAPNQHKmKrNjEDLVJoHh7bazETmwMr2SZH```

![Ethereum/EVM Wallet](apoio/Ethereum-EVM_address.jpg) Ethereum/EVM ```0x2Fe1046347e4A93C469fBDA0d84dE635e33D1a42```