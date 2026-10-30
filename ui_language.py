"""Explicit UI translations; article content and user input are never translated."""
LANGUAGES = {'English': 'en', 'Svenska': 'sv'}


def validate_language(value):
    if value not in ('en', 'sv'):
        raise ValueError('Language must be en or sv.')
    return value


SWEDISH = {'Huginn & Muninn — Settings': 'Huginn & Muninn — Inställningar',
 'Your daily perspective on the world': 'Ditt dagliga perspektiv på världen',
 'Copy support info': 'Kopiera supportinformation',
 'Appearance': 'Utseende',
 'Save settings': 'Spara inställningar',
 'Run now': 'Kör nu',
 'Stop run': 'Stoppa körning',
 'Import settings': 'Importera inställningar',
 'Reload': 'Läs in igen',
 'AI & delivery': 'AI och e-post',
 'Analysis prompt': 'Analysinstruktioner',
 'News sources': 'Nyhetskällor',
 'Schedule & deployment': 'Schema och installation',
 'Results': 'Resultat',
 'News history': 'Nyhetshistorik',
 'Search saved news': 'Sök bland sparade nyheter',
 'Search / refresh': 'Sök / uppdatera',
 'HEADLINE': 'RUBRIK',
 'SCAN DATE (LOCAL)': 'SKANNINGSDATUM (LOKALT)',
 'ARTICLE URL': 'ARTIKELADRESS',
 'View selected': 'Visa markerad',
 'Delete selected': 'Radera markerade',
 'Delete all': 'Radera alla',
 'Select all': 'Markera alla',
 'Clear selection': 'Avmarkera alla',
 'Refresh to load saved news from the deployment folder.': 'Uppdatera för att läsa sparade nyheter från '
                                                           'installationsmappen.',
 'Use ⌘/Ctrl-click to select multiple entries, or Shift-click to select a range.': 'Använd ⌘/Ctrl-klick för '
                                                                                   'att markera flera '
                                                                                   'poster, eller '
                                                                                   'Skift-klick för att '
                                                                                   'markera ett intervall.',
 'No results yet. Start a run or load the last report.': 'Inga resultat ännu. Starta en körning eller läs in '
                                                         'senaste rapporten.',
 'Preview email': 'Förhandsvisa e-post',
 'Load last report': 'Läs in senaste rapporten',
 'Follow latest': 'Följ senaste',
 'Send saved report': 'Skicka sparad rapport',
 'Retry Gmail delivery without scraping or AI.': 'Försök skicka via Gmail igen utan hämtning eller AI.',
 'ARTICLE': 'ARTIKEL',
 'PROGRESS': 'FÖRLOPP',
 '  Analysis engine  ': '  Analysmotor  ',
 '  Email delivery  ': '  E-postleverans  ',
 'Ollama server': 'Ollama-server',
 'Ollama model': 'Ollama-modell',
 'Refresh installed models': 'Uppdatera installerade modeller',
 'Refresh to list installed models.': 'Uppdatera för att lista installerade modeller.',
 'Email': 'E-post',
 'App password': 'Applösenord',
 'Articles per site': 'Artiklar per källa',
 'Show': 'Visa',
 'Search related coverage when articles cannot be read': 'Sök relaterad rapportering när artiklar inte kan '
                                                         'läsas',
 'Gemini API key': 'Gemini API-nyckel',
 'Search model': 'Sökmodell',
 'Uses Google Search via Gemini. May incur API charges. Sends the headline, URL and public lead to Google.': 'Använder '
                                                                                                             'Google '
                                                                                                             'Sök '
                                                                                                             'via '
                                                                                                             'Gemini. '
                                                                                                             'API-avgifter '
                                                                                                             'kan '
                                                                                                             'tillkomma. '
                                                                                                             'Skickar '
                                                                                                             'rubrik, '
                                                                                                             'adress '
                                                                                                             'och '
                                                                                                             'offentlig '
                                                                                                             'ingress '
                                                                                                             'till '
                                                                                                             'Google.',
 'Shape the analysis': 'Utforma analysen',
 'These instructions are used for each article by Ollama. Article text is supplied separately.': 'Instruktionerna används för varje artikel av Ollama. Artikeltexten skickas separat.',
 'Restore default prompt': 'Återställ standardinstruktioner',
 'Save settings to use your changes in future runs.': 'Spara inställningarna för att använda ändringarna vid '
                                                      'kommande körningar.',
 'Build your news desk': 'Bygg din nyhetsöversikt',
 'Add a URL. Feeds and article links are discovered automatically.': 'Lägg till en webbadress. Flöden och '
                                                                     'artikellänkar hittas automatiskt.',
 'NEWS SOURCE': 'NYHETSKÄLLA',
 'SELECTOR OVERRIDE': 'EGEN CSS-SELEKTOR',
 'ARTICLES': 'ARTIKLAR',
 'STATUS': 'STATUS',
 'Drag a source onto another row to reorder. Alt+↑/↓ also works. Save settings to keep the order; reports follow this order.': 'Dra '
                                                                                                                               'en '
                                                                                                                               'källa '
                                                                                                                               'till '
                                                                                                                               'en '
                                                                                                                               'annan '
                                                                                                                               'rad '
                                                                                                                               'för '
                                                                                                                               'att '
                                                                                                                               'ändra '
                                                                                                                               'ordningen. '
                                                                                                                               'Alt+↑/↓ '
                                                                                                                               'fungerar '
                                                                                                                               'också. '
                                                                                                                               'Spara '
                                                                                                                               'för '
                                                                                                                               'att '
                                                                                                                               'behålla '
                                                                                                                               'ordningen; '
                                                                                                                               'rapporterna '
                                                                                                                               'följer '
                                                                                                                               'samma '
                                                                                                                               'ordning.',
 'Add site': 'Lägg till källa',
 'Edit site': 'Redigera källa',
 'Delete site': 'Radera källa',
 'Test site (no AI/email)': 'Testa källa (utan AI/e-post)',
 'Let the ravens fly on schedule': 'Låt korparna flyga enligt schema',
 'Deploy a version and manage its automatic runs from one place.': 'Installera en version och hantera '
                                                                   'automatiska körningar på samma ställe.',
 '  Local deployment  ': '  Lokal installation  ',
 'Deployment folder': 'Installationsmapp',
 'Browse': 'Bläddra',
 'Cron expression': 'Cron-uttryck',
 '0 10,19 * * *  →  Every day at 10:00 and 19:00 (system timezone)': '0 10,19 * * *  →  Varje dag kl. 10:00 '
                                                                     'och 19:00 (systemets tidszon)',
 'Create a backup before replacing deployed files': 'Skapa en säkerhetskopia innan installerade filer '
                                                    'ersätts',
 'Deploy version': 'Installera version',
 'Deploy + update cron': 'Installera + uppdatera cron',
 'Backups…': 'Säkerhetskopior…',
 'Remove schedule': 'Ta bort schema',
 'Show crontab': 'Visa crontab',
 'Ready': 'Redo',
 'Clear': 'Rensa',
 'Select an article to see its lead, analysis, and extracted text.': 'Välj en artikel för att se ingress, '
                                                                     'analys och hämtad text.',
 'Waiting for articles…': 'Väntar på artiklar…',
 'Delete saved news': 'Radera sparade nyheter',
 'Saved news': 'Sparad nyhet',
 'Reading': 'Läser',
 'Analyzing': 'Analyserar',
 'Analyzed': 'Analyserad',
 'AI failed': 'AI misslyckades',
 'Interrupted': 'Avbruten',
 'Skipped': 'Överhoppad',
 'Extracted': 'Hämtad',
 'Lead paragraph': 'Ingress',
 'Analysis': 'Analys',
 'Article text': 'Artikeltext',
 'No analysis returned.': 'Ingen analys returnerades.',
 'Reading article…': 'Läser artikel…',
 'Not available yet.': 'Inte tillgängligt ännu.',
 'No readable article text was available.': 'Ingen läsbar artikeltext var tillgänglig.',
 'No entries yet': 'Inga poster ännu',
 'Run an analysis, test a site, or load the last report first.': 'Kör en analys, testa en källa eller läs in '
                                                                 'senaste rapporten först.',
 'Email layout opened in your browser. Preview does not send an email.': 'E-postvyn har öppnats i '
                                                                         'webbläsaren. Förhandsvisningen '
                                                                         'skickar ingen e-post.',
 'A run is in progress. Its live entries are shown in Results.': 'En körning pågår. Resultaten visas löpande '
                                                                 'under Resultat.',
 'Default prompt restored in the editor. Save settings to keep it.': 'Standardinstruktionerna har '
                                                                     'återställts. Spara inställningarna för '
                                                                     'att behålla dem.',
 'Choose deployment folder': 'Välj installationsmapp',
 'Could not complete action': 'Åtgärden kunde inte slutföras',
 'Articles per site must be a whole number.': 'Antal artiklar per källa måste vara ett heltal.',
 'Select or enter an Ollama model.': 'Välj eller ange en Ollama-modell.',
 'Default': 'Standard',
 'Enabled': 'Aktiverad',
 'Paused': 'Pausad',
 'Settings imported. Save config to keep them.': 'Inställningarna har importerats. Spara för att behålla '
                                                 'dem.',
 'Loading models…': 'Läser in modeller…',
 'Server changed. Refresh models again.': 'Servern har ändrats. Uppdatera modellerna igen.',
 'Could not load models. See output.': 'Kunde inte läsa in modeller. Se aktivitetsloggen.',
 'No models installed. Use ollama pull <model>.': 'Inga modeller är installerade. Använd ollama pull '
                                                  '<modell>.',
 'Configured model unavailable. Select an installed model.': 'Den valda modellen är inte tillgänglig. Välj '
                                                             'en installerad modell.',
 'Saved config.json.': 'Sparade config.json.',
 'Select a site': 'Välj en källa',
 'Select a site in the table first.': 'Välj först en källa i tabellen.',
 'Site URL': 'Källans webbadress',
 'CSS selector (optional)': 'CSS-selektor (valfritt)',
 'RSS/Atom URL (optional)': 'RSS/Atom-adress (valfritt)',
 'Articles (blank = default)': 'Artiklar (tomt = standard)',
 'Just enter a site URL. Feed and selector override automatic discovery.': 'Ange källans adress. Flöde och '
                                                                           'selektor ersätter automatisk '
                                                                           'upptäckt.',
 'Apply': 'Verkställ',
 'Cancel': 'Avbryt',
 'A run or site test is already in progress. Use Stop run before starting another.': 'En körning eller ett '
                                                                                     'test pågår redan. '
                                                                                     'Stoppa körningen innan '
                                                                                     'du startar en ny.',
 'Select a site to test first.': 'Välj först en källa att testa.',
 'Invalid article limit': 'Ogiltig artikelgräns',
 'Deployment backups': 'Säkerhetskopior av installationer',
 'UTC VERSION': 'VERSION (UTC)',
 'FILES': 'FILER',
 'SIZE': 'STORLEK',
 'No backups selected': 'Inga säkerhetskopior markerade',
 'Select one or more backup versions first.': 'Markera först en eller flera säkerhetskopior.',
 'Delete backups': 'Radera säkerhetskopior',
 'Close': 'Stäng',
 'Managed cron schedule removed.': 'Programmets cron-schema har tagits bort.',
 'No crontab installed.': 'Ingen crontab är installerad.',
 'Sending saved report to Gmail…': 'Skickar sparad rapport till Gmail…',
 'Starting analysis…': 'Startar analys…',
 'Sending the saved report only. No scraping or AI requests.': 'Skickar endast den sparade rapporten. Ingen '
                                                               'hämtning eller AI-anrop.',
 'Analysis started. Live entries and their analyses appear in Results.': 'Analysen har startat. Artiklar och '
                                                                         'analyser visas löpande under '
                                                                         'Resultat.',
 'Run in progress. Select an entry in Results to inspect it, or use Stop run.': 'Körning pågår. Välj en post '
                                                                                'under Resultat för att '
                                                                                'granska den, eller stoppa '
                                                                                'körningen.',
 'Stopping site test after the current request…': 'Stoppar testet efter pågående anrop…',
 'Stopping analysis…': 'Stoppar analysen…',
 'Stop requested. Entries received so far remain visible.': 'Stopp har begärts. Redan mottagna poster visas '
                                                            'fortfarande.',
 'Stopped': 'Stoppad',
 'Failed': 'Misslyckades',
 'Finished': 'Klar',
 'Site test finished': 'Testet är klart',
 'Running…': 'Körning pågår…',
 'Fetching the article…': 'Hämtar artikeln…',
 'Waiting for the model to return the analysis…': 'Väntar på modellens analys…',
 'Extraction only; no analysis was requested.': 'Endast hämtning; ingen analys begärdes.',
 'No article links found. Try a feed URL or CSS selector.': 'Inga artikellänkar hittades. Prova en '
                                                            'flödesadress eller CSS-selektor.',
 'No articles were received. See activity messages for details.': 'Inga artiklar mottogs. Se '
                                                                  'aktivitetsloggen för detaljer.',
 'Not enough readable article text.': 'För lite läsbar artikeltext.',
 'Run ended before this entry completed.': 'Körningen avslutades innan posten var klar.',
 'Articles per site must be a whole number from 1 to 100.': 'Antal artiklar per källa måste vara ett heltal '
                                                            'mellan 1 och 100.',
 'Language': 'Språk',
 'Default language': 'Standardspråk',
 'Use as default': 'Använd som standard',
 'Default language saved.': 'Standardspråket har sparats.',
 'No history selected': 'Ingen historik markerad',
 'Select one or more history entries first.': 'Markera först en eller flera historikposter.',
 'Delete {count} selected history entries? This cannot be undone.': 'Radera {count} markerade '
                                                                    'historikposter? Detta går inte att '
                                                                    'ångra.',
 'Delete ALL {count} history entries in {directory}? This includes entries hidden by search. This cannot be undone.': 'Radera '
                                                                                                                      'ALLA '
                                                                                                                      '{count} '
                                                                                                                      'historikposter '
                                                                                                                      'i '
                                                                                                                      '{directory}? '
                                                                                                                      'Även '
                                                                                                                      'poster '
                                                                                                                      'som '
                                                                                                                      'döljs '
                                                                                                                      'av '
                                                                                                                      'sökningen '
                                                                                                                      'raderas. '
                                                                                                                      'Detta '
                                                                                                                      'går '
                                                                                                                      'inte '
                                                                                                                      'att '
                                                                                                                      'ångra.',
 '{count} matching entries · {selected} selected · {path}': '{count} matchande poster · {selected} markerade '
                                                            '· {path}',
 '{count} sources · {enabled} enabled': '{count} källor · {enabled} aktiverade',
 'Deleted {count} saved news entries permanently. Last report and sent emails are kept.': 'Raderade {count} '
                                                                                          'sparade nyheter '
                                                                                          'permanent. '
                                                                                          'Senaste rapporten '
                                                                                          'och skickad '
                                                                                          'e-post finns '
                                                                                          'kvar.',
 'Use a Gmail app password.\n\nRun now saves and deploys your settings, then performs AI requests and sends the results by email.': 'Använd '
                                                                                                                                    'ett '
                                                                                                                                    'applösenord '
                                                                                                                                    'för '
                                                                                                                                    'Gmail.\n'
                                                                                                                                    '\n'
                                                                                                                                    'Kör '
                                                                                                                                    'nu '
                                                                                                                                    'sparar '
                                                                                                                                    'och '
                                                                                                                                    'installerar '
                                                                                                                                    'inställningarna, '
                                                                                                                                    'gör '
                                                                                                                                    'AI-anrop '
                                                                                                                                    'och '
                                                                                                                                    'skickar '
                                                                                                                                    'resultaten '
                                                                                                                                    'via '
                                                                                                                                    'e-post.',
 'Backup history is optional and can be viewed or deleted here. Failed deployments are still rolled back safely.\nOn Windows, deploy here and configure automatic runs in Task Scheduler.': 'Säkerhetskopior '
                                                                                                                                                                                            'är '
                                                                                                                                                                                            'valfria '
                                                                                                                                                                                            'och '
                                                                                                                                                                                            'kan '
                                                                                                                                                                                            'visas '
                                                                                                                                                                                            'eller '
                                                                                                                                                                                            'raderas '
                                                                                                                                                                                            'här. '
                                                                                                                                                                                            'Misslyckade '
                                                                                                                                                                                            'installationer '
                                                                                                                                                                                            'återställs '
                                                                                                                                                                                            'fortfarande '
                                                                                                                                                                                            'säkert.\n'
                                                                                                                                                                                            'I '
                                                                                                                                                                                            'Windows '
                                                                                                                                                                                            'installerar '
                                                                                                                                                                                            'du '
                                                                                                                                                                                            'här '
                                                                                                                                                                                            'och '
                                                                                                                                                                                            'schemalägger '
                                                                                                                                                                                            'i '
                                                                                                                                                                                            'Schemaläggaren.',
 'Dark': 'Mörkt',
 'Light': 'Ljust',
 '{count} entries · {analyzed} analyzed · {extracted} extracted · {skipped} skipped · {failed} failed': '{count} '
                                                                                                        'poster '
                                                                                                        '· '
                                                                                                        '{analyzed} '
                                                                                                        'analyserade '
                                                                                                        '· '
                                                                                                        '{extracted} '
                                                                                                        'hämtade '
                                                                                                        '· '
                                                                                                        '{skipped} '
                                                                                                        'överhoppade '
                                                                                                        '· '
                                                                                                        '{failed} '
                                                                                                        'misslyckade',
 '{time} elapsed': '{time} förflutet',
 'Testing site · up to {count} articles…': 'Testar källa · högst {count} artiklar…',
 'Testing {url} · limit {count} · extraction only, no AI or email.': 'Testar {url} · gräns {count} · endast '
                                                                     'hämtning, utan AI eller e-post.',
 'Loaded {count} entries from {path}.': 'Läste in {count} poster från {path}.',
 '{count} models available.': '{count} modeller tillgängliga.',
 'Analysis ready: {title}': 'Analys klar: {title}',
 'Reading: {title}': 'Läser: {title}',
 'Analyzing: {title}': 'Analyserar: {title}',
 'Site test failed: {error}': 'Testet misslyckades: {error}',
 'Could not read analysis output: {error}': 'Kunde inte läsa analysresultatet: {error}',
 'Support info copied. {version}': 'Supportinformation kopierad. {version}',
 'Analysis failed: {error}': 'Analysen misslyckades: {error}',
 'No AI analysis: {reason}': 'Ingen AI-analys: {reason}',
 'Deleted {count} deployment backup version(s).': 'Raderade {count} säkerhetskopior av installationer.',
 '{count} saved versions': '{count} sparade versioner',
 '{count} saved version': '{count} sparad version',
 'Delete {count} selected backup versions? This cannot be undone.': 'Radera {count} markerade '
                                                                    'säkerhetskopior? Detta går inte att '
                                                                    'ångra.',
 'Delete {count} selected backup version? This cannot be undone.': 'Radera {count} markerad säkerhetskopia? '
                                                                   'Detta går inte att ångra.',
 'Delete all backup versions? This cannot be undone.': 'Radera alla säkerhetskopior? Detta går inte att '
                                                       'ångra.',
 'No backup created.': 'Ingen säkerhetskopia skapades.',
 'Deployed version to {directory}.{detail} Schedule unchanged.': 'Installerade versionen i '
                                                                 '{directory}.{detail} Schemat är '
                                                                 'oförändrat.',
 'Deployed and scheduled in {directory}.{detail} Output: {path}': 'Installerade och schemalade i '
                                                                  '{directory}.{detail} Logg: {path}',
 'No saved report exists in the deployment folder yet. Finish an analysis run first.': 'Ingen sparad rapport '
                                                                                       'finns i '
                                                                                       'installationsmappen '
                                                                                       'ännu. Slutför en '
                                                                                       'analyskörning först.',
 'The last report has an invalid article list.': 'Den senaste rapporten har en ogiltig artikellista.',
 'The last report contains no articles.': 'Den senaste rapporten innehåller inga artiklar.',
 'Status: ': 'Status: ',
 'Lead\n': 'Ingress\n',
 'Analysis\n': 'Analys\n',
 'Article text\n': 'Artikeltext\n',
 'Support info copied. ': 'Supportinformation kopierad. '}
SWEDISH.update({'  SMTP connection  ': '  SMTP-anslutning  ',
 'Analysis engine': 'Analysmotor',
 'Email delivery': 'E-postleverans',
 'Email submitted to the SMTP server for {recipient}.': 'E-post har lämnats till SMTP-servern för '
                                                        '{recipient}.',
 'Encryption': 'Kryptering',
 'Enter an SMTP hostname without a URL scheme or spaces.': 'Ange ett SMTP-värdnamn utan URL-prefix eller '
                                                           'mellanslag.',
 'Enter an SMTP password or app password before sending email.': 'Ange ett SMTP-lösenord eller applösenord '
                                                                 'innan e-post skickas.',
 'Enter the recipient, sender and SMTP username.': 'Ange mottagare, avsändare och SMTP-användarnamn.',
 'Password / app password': 'Lösenord / applösenord',
 'Recipient email': 'Mottagarens e-post',
 'Retry email delivery without scraping or AI.': 'Försök skicka e-post igen utan hämtning eller AI.',
 'SMTP connection failed. Check server, port, encryption and credentials. ({error})': 'SMTP-anslutningen '
                                                                                      'misslyckades. '
                                                                                      'Kontrollera server, '
                                                                                      'port, kryptering och '
                                                                                      'inloggningsuppgifter. '
                                                                                      '({error})',
 'SMTP connection succeeded. No email was sent.': 'SMTP-anslutningen lyckades. Ingen e-post skickades.',
 'SMTP connection test': 'Test av SMTP-anslutning',
 'SMTP port': 'SMTP-port',
 'SMTP port must be a whole number from 1 to 65535.': 'SMTP-porten måste vara ett heltal mellan 1 och 65535.',
 'SMTP server': 'SMTP-server',
 'SMTP username (blank = recipient)': 'SMTP-användarnamn (tomt = mottagaren)',
 'Saved report submitted to the SMTP server.': 'Den sparade rapporten har lämnats till SMTP-servern.',
 'Sender email (blank = recipient)': 'Avsändarens e-post (tomt = mottagaren)',
 'Sending results by email…': 'Skickar resultaten via e-post…',
 'Sending saved report…': 'Skickar sparad rapport…',
 'Server requires authentication': 'Servern kräver inloggning',
 'Test connection (no email)': 'Testa anslutning (utan e-post)',
 'Testing SMTP connection; no email will be sent…': 'Testar SMTP-anslutning; ingen e-post skickas…',
 'ssl = TLS from connection start; starttls = upgrade before sign-in; none = unencrypted. Use your email provider’s SMTP settings. Gmail defaults are preserved.': 'ssl '
                                                                                                                                                                   '= '
                                                                                                                                                                   'TLS '
                                                                                                                                                                   'från '
                                                                                                                                                                   'start; '
                                                                                                                                                                   'starttls '
                                                                                                                                                                   '= '
                                                                                                                                                                   'kryptering '
                                                                                                                                                                   'före '
                                                                                                                                                                   'inloggning; '
                                                                                                                                                                   'none '
                                                                                                                                                                   '= '
                                                                                                                                                                   'okrypterat. '
                                                                                                                                                                   'Använd '
                                                                                                                                                                   'e-postleverantörens '
                                                                                                                                                                   'SMTP-inställningar. '
                                                                                                                                                                   'Gmail-inställningarna '
                                                                                                                                                                   'fungerar '
                                                                                                                                                                   'som '
                                                                                                                                                                   'tidigare.'})

REVERSE = {value: key for key, value in SWEDISH.items()}


# Match only entire presentation strings. Captures preserve titles, paths and errors.
import re
from string import Formatter


def template_pattern(template):
    parts = []
    for literal, field, _, _ in Formatter().parse(template):
        parts.append(re.escape(literal))
        if field is not None:
            parts.append('(?P<' + field + '>.+?)')
    return re.compile(''.join(parts), re.DOTALL)


TEMPLATES = [(template_pattern(english), template_pattern(swedish), english, swedish)
             for english, swedish in SWEDISH.items() if '{' in english]


def translate(text, language='en', **values):
    source = REVERSE.get(str(text), str(text))
    target = SWEDISH.get(source, source) if language == 'sv' else source
    if values:
        return target.format(**values)
    if source in SWEDISH:
        return target
    for english_pattern, swedish_pattern, english, swedish in TEMPLATES:
        match = english_pattern.fullmatch(source) or swedish_pattern.fullmatch(source)
        if match:
            return (swedish if language == 'sv' else english).format(**match.groupdict())
    return source
