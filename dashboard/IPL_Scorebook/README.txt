IPL SCOREBOOK 2008-2024 - Power BI dashboard (Power BI project, .pbip)

WHAT YOU NEED
  Power BI Desktop for Windows (a 2025 or newer version). It does not run on macOS:
  use a Windows PC, a college lab machine, or a Windows virtual machine.

OPEN IT
  1. Unzip this folder anywhere. Keep the files and folders together.
  2. Double-click IPL_Scorebook.pbip. Power BI Desktop opens the report.
  3. Click Home > Refresh. The data is stored inside the project, so this works
     with no setup and takes under a minute. Visuals are empty until you refresh.

  If Desktop says the report format needs a preview feature:
     File > Options and settings > Options > Preview features, tick
     "Power BI Project (.pbip) save option" and
     "Store reports using enhanced metadata format (PBIR)", then restart Desktop.

SUBMIT OR SHARE IT
  .pbix file:   File > Save as > choose "Power BI file (*.pbix)".
  PDF:          File > Export > Export to PDF.
  Online:       Home > Publish > My workspace.

THE THREE PAGES
  League   - The Powerplay got loud. Run rate by phase and season, boundaries vs
             dot balls, the toss, 200-plus innings, bowling first, grounds.
             Filters: season range, country.
  Players  - Nobody stays in one phase for long. Phase drift from the SCD Type 2
             dimension: a player's balls by phase each season, his spells, the most
             restless careers, moves between phases, franchise run-rate heatmap
             (click + on a franchise to split it by phase). Filters: role, player.
  Model    - Six overs tell you two-thirds of the story. Test accuracy of every
             model, the Powerplay-gap effect, every test prediction, the confusion
             matrix, chasing wickets, feature importance, confident misses.
             Filters: prediction point (A or B), model.

READ FROM THE CSV FILES INSTEAD (optional)
  Home > Transform data > Edit parameters > DataFolder = the full path of the
  data folder in this project, ending with a backslash, for example
  C:\Users\you\Downloads\IPL_Scorebook\data\   then Refresh.

WHAT IS INSIDE
  IPL_Scorebook.pbip               the file you open
  IPL_Scorebook.SemanticModel/     18 tables, 29 relationships, 53 DAX measures (TMDL)
  IPL_Scorebook.Report/            3 pages, 75 visuals, the IPL Scorebook theme
  data/                            the CSV tables the model is built from

Built by dashboard/build_pbip.py in the project repository.
