# GPS Next Move Prediction

Predpovedanie pohybu pomocou neurónovej siete (LSTM) a následné viazanie predpovede na cestnú sieť cez Mapbox API.

---

## Obsah

- [Prehľad](#prehľad)
- [Požiadavky](#požiadavky)
- [Inštalácia](#inštalácia)
- [Spustenie](#spustenie)
- [Štruktúra projektu](#štruktúra-projektu)
- [Používanie](#používanie)
- [Konfigurácia](#konfigurácia)
- [Architektúra](#architektúra)

---

## Prehľad

Projekt pozostáva z troch hlavných komponentov:

1. **Trénovanie** - LSTM sieť sa naučí predpovedať smer pohybu z histórie GPS bodov
2. **Predikcia** - model odhadne uhol budúceho pohybu z posledných 20 bodov trasy
3. **Map Matching** - predpovedaný smer sa premietne na reálnu cestnú sieť cez Mapbox

---

## Požiadavky

**PHP** ≥ 8.0

**Python** ≥ 3.9 s balíkmi:

```
torch
numpy
pandas
scikit-learn
requests
```

Nainštalujte pomocou:

```bash
pip install -r requirements.txt
```

**Mapbox API token** - potrebný pre map matching. Získate ho na [mapbox.com](https://mapbox.com).

---

## Inštalácia

```bash
git clone https://github.com/slavut1ch/gps_predictor.git
cd gps_predictor
pip install -r requirements.txt
```

Nastavte váš Mapbox token v `matching.py`:

```python
MAPBOX_TOKEN = "pk.eyJ1Ijoi..."
```

---

## Spustenie

```bash
php -S localhost:8000 -c php.ini
```

Otvorte prehliadač na `(http://localhost:8000/app.html)`.

---

## Štruktúra projektu

```
├── index.html        # Frontend - mapa Leaflet.js a ovládacie prvky
├── index.php         # Backend API (login, upload, train, predict)
├── train.py          # Trénovanie LSTM modelu
├── predict.py        # Generovanie predpovede zo uloženého modelu
├── matching.py       # Map matching cez Mapbox API
├── requirements.txt  # Python závislosti
└── storage/
    └── {username}/
        ├── csvs/     # Nahraté trénovacie CSV súbory
        ├── model.pt  # Natrénovaný model
        ├── train.pid # PID bežiaceho procesu
        └── train.log # Log trénovania
```

---

## Používanie

### 1. Prihlásenie

Zadajte ľubovoľné meno - priečinok používateľa sa vytvorí automaticky.

### 2. Trénovanie

- Nahrajte minimálne **50 CSV súborov** s GPS trasami
- Každý súbor musí obsahovať stĺpce: `unix/timestamp/time/datetime`, `lat`, `lon`
- Kliknite **Start training** - trénovanie beží na pozadí, priebeh je viditeľný v logu

### 3. Predikcia

- Nahrajte CSV trasu na zobrazenie
- Pohybujte sa po trase tlačidlami alebo klávesami `←` `→`
- Červená bodka = predpovedaný smer pohybu
- Zaškrtnite **Map matching** pre zobrazenie bodu priamo na ceste (oranžová bodka)

### Formát CSV

```csv
unix,lat,lon
1708419600,48.1486,17.1077
1708419601,48.1487,17.1079
...
```

---

## Architektúra

### Model

LSTM sieť s 3 vrstvami a 128 skrytými jednotkami. Vstupom je sekvencia 20 GPS bodov, každý reprezentovaný 9 príznakmi:

- Δlat, Δlon (pohyb v metroch)
- Rýchlosť, zrýchlenie
- sin/cos azimutu
- Zakrivenie trasy
- sin/cos času dňa

Výstupom je klasifikácia do 36 smerových tried (každá = 10°).

### Trénovanie na pozadí

PHP spustí Python ako samostatný OS proces, uloží PID a JavaScript každé 3 sekundy pýta stav. Môžete zavrieť prehliadač a trénovanie pokračuje na serveri.
