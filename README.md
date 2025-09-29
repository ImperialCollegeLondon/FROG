![GitHub tag (with filter)](https://img.shields.io/github/v/tag/ImperialCollegeLondon/FROG)
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-6-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
[![GitHub](https://img.shields.io/github/license/ImperialCollegeLondon/FROG)](https://raw.githubusercontent.com/ImperialCollegeLondon/FROG/main/LICENCE.txt)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/ImperialCollegeLondon/FROG/main.svg)](https://results.pre-commit.ci/latest/github/ImperialCollegeLondon/FROG/main)
[![Test and build](https://github.com/ImperialCollegeLondon/FROG/actions/workflows/ci.yml/badge.svg)](https://github.com/ImperialCollegeLondon/FROG/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ImperialCollegeLondon/FROG/graph/badge.svg?token=4UILYHPMJT)](https://codecov.io/gh/ImperialCollegeLondon/FROG)

# FROG

FROG (**F**ar infra**R**ed **O**bservation **G**UI) is software for controlling a
spectrometer system developed by Imperial College London's [Space and Atmospheric
Physics group], written in Python and with a graphical interface using the [PySide6 Qt
bindings].

Emissivity of the Earth's different surface types helps determine the efficiency with
which the planet radiatively cools to space and is a critical variable in climate
models. However, to date, most measurements of surface emissivity have been made in the
mid-infrared. The [FINESSE] project is novel in employing a ground-based system capable
of extending these datasets into the far-infrared. The system is tuned in particular for
targeting ice and snow, as the response of the climate to global warming is observed to
be most rapid in Arctic regions. Far-infrared emissivity data provided by FINESSE will
inform climate modelling studies seeking to better understand this rapid change. They
will also help to validate emissivity retrievals from upcoming satellite instruments
focusing on the far-infrared which will be deployed by ESA ([FORUM]) and NASA
([PREFIRE]).

This software is currently being adapted as part of a second project &ndash; [UNIRAS]
&ndash; to deploy a modified version of the equipment on the UK’s [Facility for Airborne
Atmospheric Measurements] aircraft.

[Space and Atmospheric Physics group]: https://www.imperial.ac.uk/physics/research/communities/space-plasma-climate/
[PySide6 Qt bindings]: https://pypi.org/project/PySide6/
[FINESSE]: https://www.imperial.ac.uk/a-z-research/space-and-atmospheric-physics/research/missions-and-projects/atmospheric-missions/finesse/
[FORUM]: https://www.esa.int/Applications/Observing_the_Earth/FutureEO/FORUM
[PREFIRE]: https://science.nasa.gov/mission/prefire/
[UNIRAS]: https://www.imperial.ac.uk/space-and-atmospheric-physics/research/missions-and-projects/atmospheric-missions/uniras/
[Facility for Airborne Atmospheric Measurements]: https://www.faam.ac.uk/

## For developers

Technical documentation is available on [FROG's GitHub Pages site](https://imperialcollegelondon.github.io/FROG/).

This is a Python application that uses [uv](https://docs.astral.sh/uv/) for packaging
and dependency management. It also provides [pre-commit](https://pre-commit.com/) hooks
for various linters and formatters and automated tests using
[pytest](https://pytest.org/) and [GitHub Actions](https://github.com/features/actions).
Pre-commit hooks are automatically kept updated with a dedicated GitHub Action.

To get started:

1. [Download and install uv](https://docs.astral.sh/uv/getting-started/installation/) following the
   instructions for your OS.
1. Clone this repository and make it your working directory
1. Set up the virtual environment:

   ```bash
   uv sync
   ```

1. Install the git hooks:

   ```bash
   pre-commit install
   ```

1. **Optional:** [Activate your virtual
   environment.](https://docs.astral.sh/uv/pip/environments/#using-a-virtual-environment) This makes
   the various tools installed into your virtual environment, such as Python and `pytest` available on the path. Alternatively, you can prefix the below commands with `uv run`.

1. Run the main app:

   ```bash
   python -m frog
   ```

1. Run the tests:

   ```bash
   pytest
   ```

1. Build the user guide:

   1. Install [pandoc](https://pandoc.org/installing.html)

   1. ```bash
      python docs/gen_user_guide.py
      ```

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://www.imperial.ac.uk/admin-services/ict/self-service/research-support/rcs/service-offering/research-software-engineering/"><img src="https://avatars.githubusercontent.com/u/23149834?v=4?s=100" width="100px;" alt="Alex Dewar"/><br /><sub><b>Alex Dewar</b></sub></a><br /><a href="https://github.com/ImperialCollegeLondon/FROG/commits?author=alexdewar" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://dc2917.github.io/"><img src="https://avatars.githubusercontent.com/u/45606273?v=4?s=100" width="100px;" alt="Dan Cummins"/><br /><sub><b>Dan Cummins</b></sub></a><br /><a href="https://github.com/ImperialCollegeLondon/FROG/commits?author=dc2917" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/CWestICL"><img src="https://avatars.githubusercontent.com/u/108276827?v=4?s=100" width="100px;" alt="CWestICL"/><br /><sub><b>CWestICL</b></sub></a><br /><a href="https://github.com/ImperialCollegeLondon/FROG/commits?author=CWestICL" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://www.imperial.ac.uk/admin-services/ict/self-service/research-support/rcs/service-offering/research-software-engineering/"><img src="https://avatars.githubusercontent.com/u/6095790?v=4?s=100" width="100px;" alt="Diego Alonso Álvarez"/><br /><sub><b>Diego Alonso Álvarez</b></sub></a><br /><a href="https://github.com/ImperialCollegeLondon/FROG/commits?author=dalonsoa" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://www.imperial.ac.uk/research-software-engineering"><img src="https://avatars.githubusercontent.com/u/6853046?v=4?s=100" width="100px;" alt="James Paul Turner"/><br /><sub><b>James Paul Turner</b></sub></a><br /><a href="https://github.com/ImperialCollegeLondon/FROG/commits?author=jamesturner246" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jonemurray"><img src="https://avatars.githubusercontent.com/u/116724201?v=4?s=100" width="100px;" alt="jonemurray"/><br /><sub><b>jonemurray</b></sub></a><br /><a href="#ideas-jonemurray" title="Ideas, Planning, & Feedback">🤔</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!
