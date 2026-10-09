"""Import every model module so that Base.metadata is complete."""

from app.core.adapters import models as _adapters  # noqa: F401
from app.core.assets import models as _assets  # noqa: F401
from app.core.audit import models as _audit  # noqa: F401
from app.core.files import models as _files  # noqa: F401
from app.core.systems import models as _systems  # noqa: F401
from app.core.tenants import models as _tenants  # noqa: F401
from app.core.users import models as _users  # noqa: F401
from app.db import mssql as _mssql  # noqa: F401
from app.db.base import Base
from app.modules.agenthub import models as _agenthub  # noqa: F401
from app.modules.devtracker import models as _devtracker  # noqa: F401
from app.modules.discoveryq import models as _discoveryq  # noqa: F401
from app.modules.exmigrate import models as _exmigrate  # noqa: F401
from app.modules.flowdesk import models as _flowdesk  # noqa: F401
from app.modules.interfaces import models as _interfaces  # noqa: F401
from app.modules.ontomap import models as _ontomap  # noqa: F401
from app.modules.specforge import models as _specforge  # noqa: F401

metadata = Base.metadata
