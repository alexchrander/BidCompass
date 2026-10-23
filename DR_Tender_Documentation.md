## DR (tender) documents: what are we looking for in the tender documents?

Within the DR (tender) documents retrieved from the dados.gov.pt announcements dataset, we are looking for the class and categories incl. subcategories:
* **Classes:** determined from the base price excl. VAT found in section 5 (PROCESSO)
* **Categories incl. subcategories:** determined by the qualification requirements found in section 12 (DOCUMENTOS DE HABILITAÇÃO)

## Alvará matching: what to extract from DR notices

| Notice field (PT) | English | Example | Used for | IMPIC field |
|---|---|---|---|---|
| 12 – Documentos de habilitação | Qualification documents | Section header | Locates the licence requirement | n/a |
| Habilitação para o exercício da atividade profissional | Professional activity qualification required | Sim / Não | If "Não", no licence check needed | n/a |
| Tipo | Accepted document type | Alvará, Certificado de Empreiteiro de Obras Públicas, declaração emitida pelo IMPIC | Which IMPIC registers to check (alvará and certificado) | Register type |
| Categoria | Category | 2.ª Categoria | Required category | Categoria |
| Subcategoria | Subcategory | 8.ª subcategoria | Required subcategory | Subcategoria |
| Regra da classe | Class rule | "de classe que cubra o valor total da proposta" | Whether class must cover the full value or only specialised works | Classe |
| Classe (if stated) | Class | classe 3 | Use directly, no calculation | Classe |
| 5 – Preço base s/IVA | Base price excl. VAT | 84.431,00 EUR | Converted to required class (≤ €200k = classe 1, ≤ €400k = classe 2, ...) | Classe |
| Procedimento com lotes? | Procedure with lots? | Sim / Não | If "Sim", derive class per lot from the lot's base price | Classe |

## IMPIC alvará reference

### Classes (Classes de habilitações)
Source: Portaria n.º 212/2022 (in force since 24 Aug 2022)

| Classe | Max. works value (EUR) |
|---|---|
| 1 | 200,000 |
| 2 | 400,000 |
| 3 | 800,000 |
| 4 | 1,600,000 |
| 5 | 3,200,000 |
| 6 | 6,400,000 |
| 7 | 12,500,000 |
| 8 | 19,000,000 |
| 9 | Above 19,000,000 |

### Categories and subcategories (Categorias e subcategorias)
Source: Lei n.º 41/2015, Anexo I. Code = category.subcategory (e.g. "8.ª subcategoria da 2.ª categoria" = 2.8)

| Code | Subcategory (PT) | English |
|---|---|---|
| **1** | **Edifícios e património construído** | **Buildings and built heritage** |
| 1.1 | Estruturas e elementos de betão | Concrete structures and elements |
| 1.2 | Estruturas metálicas | Steel structures |
| 1.3 | Estruturas de madeira | Timber structures |
| 1.4 | Alvenarias, rebocos e assentamento de cantarias | Masonry, plastering and stonework |
| 1.5 | Estuques, pinturas e outros revestimentos | Stucco, painting and other finishes |
| 1.6 | Carpintarias | Carpentry |
| 1.7 | Trabalhos em perfis não estruturais | Non-structural profile work |
| 1.8 | Canalizações e condutas em edifícios | Plumbing and ducts in buildings |
| 1.9 | Instalações sem qualificação específica | Installations without specific qualification |
| 1.10 | Restauro de bens imóveis histórico-artísticos | Restoration of historic buildings |
| **2** | **Vias de comunicação, obras de urbanização e outras infraestruturas** | **Transport routes, urban works and other infrastructure** |
| 2.1 | Vias de circulação rodoviária e aeródromos | Roads and airfields |
| 2.2 | Vias de circulação ferroviária | Railways |
| 2.3 | Pontes e viadutos de betão | Concrete bridges and viaducts |
| 2.4 | Pontes e viadutos metálicos | Steel bridges and viaducts |
| 2.5 | Obras de arte correntes | Minor civil structures (culverts, small bridges) |
| 2.6 | Saneamento básico | Water supply and sewerage |
| 2.7 | Oleodutos e gasodutos | Oil and gas pipelines |
| 2.8 | Calcetamentos | Paving (stone/cobble) |
| 2.9 | Ajardinamentos | Landscaping |
| 2.10 | Infraestruturas de desporto e lazer | Sports and leisure facilities |
| 2.11 | Sinalização não elétrica e dispositivos de proteção e segurança | Non-electrical signage and safety barriers |
| **3** | **Obras hidráulicas** | **Hydraulic works** |
| 3.1 | Obras fluviais e aproveitamentos hidráulicos | River works and hydraulic schemes |
| 3.2 | Obras portuárias | Port works |
| 3.3 | Obras de proteção costeira | Coastal protection |
| 3.4 | Barragens e diques | Dams and dykes |
| 3.5 | Dragagens | Dredging |
| 3.6 | Emissários | Outfalls |
| **4** | **Instalações elétricas e mecânicas** | **Electrical and mechanical installations** |
| 4.1 | Instalações elétricas de utilização de baixa tensão (até 50 kVA) | Low-voltage electrical installations (up to 50 kVA) |
| 4.2 | Postos de transformação até 250 kVA | Transformer stations up to 250 kVA |
| 4.3 | Postos de transformação acima de 250 kVA | Transformer stations above 250 kVA |
| 4.4 | Redes e instalações elétricas até 30 kV | Electrical networks up to 30 kV |
| 4.5 | Redes e instalações elétricas acima de 30 kV | Electrical networks above 30 kV |
| 4.6 | Instalações de produção de energia elétrica até 30 kV | Power generation up to 30 kV |
| 4.7 | Instalações de produção de energia elétrica acima de 30 kV | Power generation above 30 kV |
| 4.8 | Instalações de tração elétrica | Electric traction systems |
| 4.9 | Infraestruturas de telecomunicações | Telecom infrastructure |
| 4.10 | Sistemas de extinção de incêndios, de segurança e de deteção | Fire suppression, security and detection |
| 4.11 | Instalações de elevação | Lifts and elevators |
| 4.12 | Aquecimento, ventilação, ar condicionado e refrigeração | HVAC and refrigeration |
| 4.13 | Estações de tratamento ambiental | Environmental treatment plants |
| 4.14 | Redes e ramais de distribuição de gás, instalações e aparelhos a gás | Gas distribution and appliances |
| 4.15 | Armazenamento de produtos de petróleo e postos de abastecimento | Fuel storage and filling stations |
| 4.16 | Redes de ar comprimido e vácuo | Compressed air and vacuum networks |
| 4.17 | Instalações de apoio e sinalização em sistemas de transportes | Transport signalling and support systems |
| 4.18 | Gestão técnica centralizada | Building management systems |
| 4.19 | Outras instalações mecânicas e eletromecânicas | Other mechanical and electromechanical installations |
| **5** | **Outros trabalhos** | **Other works** |
| 5.1 | Demolições | Demolition |
| 5.2 | Movimentação de terras | Earthworks |
| 5.3 | Túneis e outros trabalhos de geotecnia | Tunnels and other geotechnical works |
| 5.4 | Fundações especiais | Special foundations |
| 5.5 | Reabilitação de elementos estruturais de betão | Concrete structural rehabilitation |
| 5.6 | Paredes de contenção e ancoragens | Retaining walls and anchoring |
| 5.7 | Drenagens e tratamento de taludes | Drainage and slope treatment |
| 5.8 | Armaduras para betão armado | Rebar for reinforced concrete |
| 5.9 | Reparações e tratamentos superficiais em estruturas metálicas | Steel structure repair and surface treatment |
| 5.10 | Cofragens | Formwork |
| 5.11 | Impermeabilizações e isolamentos | Waterproofing and insulation |
| 5.12 | Andaimes e outras estruturas provisórias | Scaffolding and temporary structures |
| 5.13 | Caminhos agrícolas e florestais | Agricultural and forest roads |