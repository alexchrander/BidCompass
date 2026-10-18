# BidCompass: Portal BASE data brief

Context for discussing next steps. BidCompass is an AI eligibility check for first-time public tender bidders in Portugal. This brief describes the two Portal BASE datasets already downloaded. Field meanings are inferred from Portuguese field names and sample values, not from official documentation. Fill rates are measured on the first 20,000 rows of the 2025 files.

## What we have

Source: dados.gov.pt, downloaded by `python -m ingest.base <kind> <years...>`.

| Dataset | Dataset ID | Raw location | Format |
|---|---|---|---|
| contratos (awarded contracts) | `66d72d488ca4b7cb2de28712` | `data/raw/base/contratos_<year>/Contratos<year>.json` (ZIP kept alongside) | JSON array |
| anuncios (tender announcements) | `66d72fbc58cd7a63dae28712` | `data/raw/base/anuncios_<year>/anuncios<year>.json` | JSON array |

- Years available and downloaded: 2012-2026. The 2026 files are partial; re-run the 2026 download to refresh them.
- The dataset ID stays the same over time; new yearly files are added as resources under it. The downloader re-fetches a file only if its checksum changed.
- Nothing is processed yet: no Parquet output, no cleaning, no joins.
- Contracts files are large (about 100-420 MB each as JSON).

## Records by year

| Year | Contracts | Announcements |
|---|---|---|
| 2012 | 65,504 | 6,680 |
| 2013 | 84,652 | 8,194 |
| 2014 | 103,923 | 9,097 |
| 2015 | 108,190 | 9,563 |
| 2016 | 115,073 | 10,609 |
| 2017 | 128,616 | 14,072 |
| 2018 | 127,936 | 13,787 |
| 2019 | 145,517 | 17,327 |
| 2020 | 176,533 | 19,071 |
| 2021 | 187,438 | 19,648 |
| 2022 | 176,605 | 21,153 |
| 2023 | 194,013 | 30,248 |
| 2024 | 227,484 | 27,772 |
| 2025 | 247,971 | 33,521 |
| 2026 (partial) | 194,863 | 25,200 |

Schema is stable across all years: 39 contract fields and 20 announcement fields. This was checked on the first 2,000 records of each file, not every record.

## Contratos: 39 fields

| Field | Meaning | Filled | Example |
|---|---|---|---|
| `idcontrato` | Unique contract ID | 100% | 11203242 |
| `nAnuncio` | Number of the linked announcement (joins to `anuncios.nAnuncio`) | 17% | 28167/2024 |
| `TipoAnuncio` | Type of the linked announcement | 17% | Anúncio de procedimento |
| `idINCM` | INCM (Official Gazette) ID of the linked announcement | 17% | 418510958 |
| `tipoContrato` | Contract type (list) | 100% | Aquisição de serviços |
| `idprocedimento` | Procedure ID | 100% | 7450730 |
| `tipoprocedimento` | Procedure type | 100% | Consulta Prévia |
| `objectoContrato` | Contract subject | 100% | Técnicos da Loja de Cidadão… |
| `descContrato` | Contract description | 100% | CONTRATO DE AVENÇA |
| `adjudicante` | Buyer(s), as "NIF - name" | 100% | 506874320 - Município de Valpaços |
| `adjudicatarios` | Winner(s), as "NIF - name" | 100% | 510273777 - CARNUTALHO… |
| `dataPublicacao` | Publication date (dd/mm/yyyy) | 100% | 03/02/2025 |
| `dataCelebracaoContrato` | Contract signing date | 100% | 29/01/2025 |
| `precoContratual` | Contract price (EUR, number) | 100% | 12650.0 |
| `cpv` | CPV codes and descriptions (list) | 100% | 98000000-3 - Outros serviços… |
| `prazoExecucao` | Execution period (days) | 100% | 331 |
| `localExecucao` | Place of execution (list) | 100% | Portugal, Vila Real, Valpaços |
| `fundamentacao` | Legal basis for the procedure choice | 100% | Artigo 20.º, n.º 1, alínea c) CCP |
| `ProcedimentoCentralizado` | Centralised procurement, Sim/Não | 100% | Não |
| `numAcordoQuadro` | Framework agreement number | 15% | 6135510 |
| `DescrAcordoQuadro` | Framework agreement description | 15% | 87/2022 - Acordo quadro… |
| `precoBaseProcedimento` | Base (maximum) price of the procedure | 100% | 12650.0 |
| `dataDecisaoAdjudicacao` | Award decision date | 100% | 23/01/2025 |
| `dataFechoContrato` | Contract closing date | 25% | 31/12/2025 |
| `PrecoTotalEfetivo` | Actual total price (after changes) | 100% | 12650.0 |
| `regime` | Legal regime | 100% | Código dos Contratos Públicos (DL 111-B/2017) |
| `justifNReducEscrContrato` | Reason for no written contract (list) | 14% | Artigo 6.º-A… |
| `tipoFimContrato` | How the contract ended | 25% | O cumprimento… |
| `CritMateriais` | Material criteria applied, Sim/Não | 100% | Não |
| `concorrentes` | Competing bidders (list) | 47% | 514992093-PROXSYS SOLUTIONS, LDA. |
| `linkPecasProc` | Link to procedure documents | 54% | https://community.vortal.biz/… |
| `Observacoes` | Free-text notes | 4% | Cab: 2025/013 |
| `ContratEcologico` | Green procurement, Sim/Não | 100% | Não |
| `Ano` | Year of the file | 100% | 2025 |
| `fundamentAjusteDireto` | Justification for a direct award | 6% | ausência de recursos próprios |
| `adjudicatarioPMEs` | Winner NIFs flagged as SMEs (list) | 84% | 980379563 |
| `NUTs` | NUTS region (list) | 42% | PT200 - Região Autónoma dos Açores |
| `Lotes` | Lots covered (list) | 23% | lote5 |
| `TipoCriterioAdjudicacao` | Award criterion type | 100% | Monofator |

## Anuncios: 20 fields

| Field | Meaning | Filled | Example |
|---|---|---|---|
| `nAnuncio` | Announcement number | 100% | 19099/2025 |
| `IdIncm` | INCM (Official Gazette) ID | 100% | 419307447 |
| `dataPublicacao` | Publication date (dd/mm/yyyy) | 100% | 17/07/2025 |
| `nifEntidade` | Buyer NIF | 100% | 500745471 |
| `designacaoEntidade` | Buyer name | 100% | Santa Casa da Misericórdia de Lisboa |
| `descricaoAnuncio` | What is being procured | 100% | Empreitada de Conceção-Construção… ETAR de Ouca |
| `url` | PDF of the notice in Diário da República | 100% | https://files.diariodarepublica.pt/… |
| `numDR` | Gazette issue number (string) | 100% | 136 |
| `serie` | Gazette series (string) | 100% | 2 |
| `tipoActo` | Notice type (procedure, amendment, …) | 100% | Anúncio de procedimento |
| `tiposContrato` | Contract type(s) (list) | 100% | Empreitadas de obras públicas |
| `PrecoBase` | Base price (string) | 100% | 4400000.00 |
| `CPVs` | CPV codes (list) | 100% | 45232151-5 - Obras de renovação… |
| `modeloAnuncio` | Procedure model | 100% | Concurso público |
| `Ano` | Year | 100% | 2025 |
| `CriterAmbient` | Environmental criteria, Sim/Não | 100% | Não |
| `PrazoPropostas` | Bid period (days) | 100% | 82 |
| `PecasProcedimento` | Link to procedure documents | 100% | https://www.acingov.pt/… |
| `DataLimitePropostas` | Bid deadline | 98% | 27/08/2025 |
| `Lotes` | Lots (list of descriptions) | 27% | Lote 1 - Aquisição de monitores… |

## Sample records (2025)

Contracts (buyer / winner / price / CPV):

| Buyer | Winner | Price | CPV |
|---|---|---|---|
| ULS Santa Maria | Baxter Médico Farmacêutica | €15,049.34 | 33600000-6 Pharmaceutical products |
| ULS do Nordeste | Lundbeck Portugal | €319.90 | 33600000-6 Pharmaceutical products |
| Freguesia de Vila Real | Espaço Genial - Construção Civil | €24,801.03 | 45259000-7 Repair/maintenance of installations |
| Universidade do Minho | Smile - Viagens e Turismo | €259.36 | 60400000-2 Air transport; 98341000-5 Accommodation |
| ULS de São José | Topsurge - Art. e Equip. Cirúrgicos | €5,615.40 | 33100000-1 Medical equipment |

Announcements (buyer / description / type / base price / CPV / deadline):

| Buyer | Description | Type | Base price | CPV | Deadline |
|---|---|---|---|---|---|
| Município do Porto | Renting and maintenance of copy/print equipment | Amendment (7 lots) | €747,333.16 | 30120000-6 | 26/05/2025 |
| Universidade Politécnica de Coimbra | Cleaning services and hygiene products | Procedure | €1,609,024.00 | 90910000-9 | 14/08/2025 |
| Município da Guarda | Christmas lighting rental 2025 | Procedure | €149,500.00 | 71318100-1 | 01/10/2025 |
| ULS do Baixo Alentejo | Urology prostheses and other items (8 lots) | Procedure | €154,306.63 | 33140000-3 | 15/12/2025 |
| Carris (Lisbon) | Public works, station exterior infrastructure (2 lots) | Procedure | €1,150,000.00 | 45231110-9 | 19/04/2025 |

## Data quality notes and caveats

- **Linking announcements to contracts:** only about 17% of contracts carry `nAnuncio`, `TipoAnuncio` and `idINCM`. Most are direct awards with no announcement, so roughly 1 in 6 contracts can be joined to an announcement.
- **Announcement types:** `tipoActo` includes amendment notices, not just new procedures. These need filtering for "open tender" use cases.
- **Mixed types:** `PrecoBase` is a string in announcements while `precoContratual` is a number in contracts. `numDR` and `serie` are strings holding numbers. `idcontrato` and `idprocedimento` are numeric in some readers and strings in others.
- **Dates:** dd/mm/yyyy strings in both files, and some are empty strings (e.g. `dataCelebracaoContrato` was empty on one sampled row).
- **Names:** can contain HTML entities (e.g. `&amp;`). Buyer and winner fields are "NIF - name" strings and need splitting. `concorrentes` uses "NIF-NAME" with no spaces around the hyphen.
- **File year vs publication date:** the contracts file is keyed by a different year than the publication date in some rows (a 2025 file included a contract published in 2024).
- **Multi-valued fields:** buyers, winners, CPVs, locations, lots and competitors are lists, so one contract can have several winners or CPVs.
- **2026 is partial** (194,863 contracts, 25,200 announcements at download time).
- Schema consistency was sampled (first 2,000 records per file), and fill rates come from the first 20,000 rows of the 2025 files only.

## Fields most relevant to first-time bidders

- `concorrentes`: competitor counts per contract (only 47% filled).
- `adjudicatarioPMEs`: whether winners are SMEs.
- `precoBaseProcedimento` against `precoContratual`: how far prices land below the base price.
- `tipoprocedimento`, `modeloAnuncio` and `fundamentAjusteDireto`: procedure types and direct-award reasons.
- `cpv`, `localExecucao` and `NUTs`: matching by sector and region.
- `DataLimitePropostas` and `PrazoPropostas`: time available to respond to a tender.
- `linkPecasProc`, `PecasProcedimento` and `url`: links to tender documents and notices, useful later for extracting eligibility requirements.

## Other sources in the ingest layer

- `ingest/ted.py`: TED API query for Portuguese `cn-standard` notices. Not yet run.
- `ingest/impic.py`: stub, reads a manual `data/raw/impic/licences.csv` (nif, category, subcategory, class). IMPIC API access is still to be requested.
- `ingest/dre.py`: stub, no known public API for Diário da República 2.ª série Parte L.

## Open questions to discuss

1. Which contract and announcement fields should the cleaned dataset keep, and in what schema (Parquet)?
2. How should we handle contracts without an announcement, given only about 17% link?
3. How do we define "first-time bidder" friendly tenders (price size, procedure type, number of competitors, past winners)?
4. How do we get eligibility requirements from the tender documents (PDFs behind `url` and `PecasProcedimento`)?
5. Do we need all 15 years, or only recent years (for example 2022 onwards)?
