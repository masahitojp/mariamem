"""Version-range and structure-verified driver hooks; imported only by explicit routing.install()."""
import importlib
import importlib.metadata
import re

_STABLE_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<micro>\d+))?(?:\.post\d+)?$"
)

PYMYSQL_RANGE = ((1, 1, 0), (2, 0, 0), ">=1.1,<2")
CONNECTOR_RANGE = ((9, 0, 0), (27, 0, 0), ">=9.0,<27")
MYSQLCLIENT_RANGE = ((2, 2, 0), (3, 0, 0), ">=2.2,<3")
SQLALCHEMY_RANGE = ((2, 0, 0), (2, 2, 0), ">=2.0,<2.2")

_MYSQLDB_POS_ARGS = (
    "host", "user", "password", "database", "port",
    "unix_socket", "conv", "connect_timeout", "compress",
    "named_pipe", "init_command", "read_default_file", "read_default_group",
    "client_flag", "ssl", "ssl_mode", "local_infile",
    "read_timeout", "write_timeout", "charset", "auth_plugin",
    "server_public_key_path", "local_infile_dir",
)


def _parse_stable_version(text):
    if not isinstance(text, str):
        return None
    match = _STABLE_VERSION_RE.match(text.strip())
    if match is None:
        return None
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("micro") or 0),
    )


def check_package_version(
    registry,
    package,
    minimum,
    upper,
    *,
    code,
    action,
    driver=None,
    missing_code="driver_unavailable",
    missing_action=None,
):
    try:
        actual = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError as error:
        raise registry._error(
            missing_code,
            missing_action or "Inspect the driver import cause or use explicit child configuration.",
            driver=driver,
        ) from error
    parsed = _parse_stable_version(actual)
    if parsed is None or not (minimum <= parsed < upper):
        raise registry._error(code, action, driver=driver)
    return actual


def check_sqlalchemy_version(registry):
    minimum, upper, spec = SQLALCHEMY_RANGE
    return check_package_version(
        registry,
        "SQLAlchemy",
        minimum,
        upper,
        code="unsupported_adapter_version",
        action=f"Use SQLAlchemy{spec} or explicit child configuration.",
        missing_code="adapter_unavailable",
        missing_action="Install the routing-sqlalchemy extra or pass child settings explicitly.",
    )


def _load(registry, package, module, version_range):
    minimum, upper, spec = version_range
    check_package_version(
        registry,
        package,
        minimum,
        upper,
        code="unsupported_driver_version",
        action=f"Use {package}{spec} or explicit child configuration.",
        driver=module,
    )
    try:
        return importlib.import_module(module)
    except (ImportError, AttributeError, OSError) as error:
        raise registry._error(
            "driver_unavailable",
            "Inspect the driver import cause or use explicit child configuration.",
            driver=module,
        ) from error


def _require_callable(registry, owner, attr, *, package, spec, driver):
    value = getattr(owner, attr, None)
    if not callable(value):
        raise registry._error(
            "unsupported_driver_version",
            f"Installed {package} lacks expected hook target {attr}; use {package}{spec} or explicit child configuration.",
            driver=driver,
        )
    return value


def _selected(registry, connection, host, port, schema):
    owner = getattr(connection, "_mariamem_registry", None)
    if owner is not None and owner is not registry:
        raise registry._error("held_connection", "Create a new connection under this registry.")
    if owner is None and not registry._match(host, port, schema):
        return False
    registry._schema(schema)
    return True


def install_driver(registry, name):
    if name == "pymysql":
        _pymysql(registry)
    elif name == "mysql.connector":
        _connector(registry)
    elif name == "MySQLdb":
        _mysqldb(registry)
    else:
        raise registry._error(
            "unsupported_driver",
            "Select pymysql, mysql.connector, or MySQLdb, or use explicit configuration.",
            driver=name,
        )


def _pymysql(registry):
    driver = _load(registry, "PyMySQL", "pymysql", PYMYSQL_RANGE)
    spec = PYMYSQL_RANGE[2]
    cls = getattr(getattr(driver, "connections", None), "Connection", None)
    err_cls = getattr(getattr(driver, "err", None), "Error", None)
    if not isinstance(cls, type) or not isinstance(err_cls, type):
        raise registry._error(
            "unsupported_driver_version",
            f"Installed PyMySQL lacks expected Connection/Error classes; use PyMySQL{spec} or explicit child configuration.",
            driver="pymysql",
        )
    original_init = _require_callable(registry, cls, "__init__", package="PyMySQL", spec=spec, driver="pymysql")
    original_connect = _require_callable(registry, cls, "connect", package="PyMySQL", spec=spec, driver="pymysql")

    def initialize(connection, *args, **kw):
        schema = kw.get("database") if kw.get("database") is not None else kw.get("db")
        if registry._match(kw.get("host"), kw.get("port"), schema):
            if kw.get("read_default_file") or kw.get("read_default_group"):
                raise registry._error("option_file", "Resolve this profile to explicit test settings.", driver="pymysql")
            if kw.get("unix_socket"):
                raise registry._error("transport_conflict", "Use the registered TCP profile explicitly.", driver="pymysql")
        return original_init(connection, *args, **kw)

    def connect(connection, sock=None):
        if not _selected(registry, connection, connection.host, connection.port, connection.db):
            return original_connect(connection, sock)
        if sock is not None or connection.unix_socket:
            raise registry._error("transport_conflict", "Use the registered TCP profile explicitly.", driver="pymysql")
        if getattr(connection, "_ssl_required", connection.ssl):
            raise registry._error("tls_unavailable", "This child has no TLS; select an explicit local test profile.", driver="pymysql")

        def close():
            try:
                connection.close()
            except err_cls as error:
                if str(error) != "Already closed":
                    raise

        def redirected(info):
            connection.host, connection.port = info["host"], info["port"]
            connection.user, connection.password = info["user"], info["password"].encode()
            return original_connect(connection, sock)

        return registry._connect(connection, redirected, close, "pymysql")

    registry._patch(cls, "__init__", initialize)
    registry._patch(cls, "connect", connect)


def _connector(registry):
    driver = _load(registry, "mysql-connector-python", "mysql.connector", CONNECTOR_RANGE)
    spec = CONNECTOR_RANGE[2]
    try:
        abstracts_mod = importlib.import_module("mysql.connector.abstracts")
    except (ImportError, AttributeError, OSError) as error:
        raise registry._error(
            "driver_unavailable",
            "Inspect the driver import cause or use explicit child configuration.",
            driver="mysql.connector",
        ) from error
    abstract = getattr(abstracts_mod, "MySQLConnectionAbstract", None)
    if not isinstance(abstract, type):
        raise registry._error(
            "unsupported_driver_version",
            f"Installed mysql-connector-python lacks MySQLConnectionAbstract; use mysql-connector-python{spec} or explicit child configuration.",
            driver="mysql.connector",
        )
    original_connect = _require_callable(
        registry, abstract, "connect", package="mysql-connector-python", spec=spec, driver="mysql.connector"
    )
    original_factory = _require_callable(
        registry, driver, "connect", package="mysql-connector-python", spec=spec, driver="mysql.connector"
    )

    def factory(*args, **kw):
        if registry._match(kw.get("host"), kw.get("port"), kw.get("database")):
            if args or any(kw.get(k) for k in ("pool_name", "pool_size", "option_files",
                                               "read_default_file", "dns_srv", "failover")):
                raise registry._error("unsupported_factory", "Use the enrolled unpooled factory or explicit configuration.", driver="mysql.connector")
        return original_factory(*args, **kw)

    def connect(connection, **kw):
        host, port = kw.get("host", getattr(connection, "_host", None)), kw.get("port", getattr(connection, "_port", None))
        schema = kw.get("database", getattr(connection, "_database", None))
        if not _selected(registry, connection, host, port, schema):
            return original_connect(connection, **kw)
        if any(kw.get(k) for k in ("unix_socket", "option_files", "read_default_file", "ssl_ca",
                                   "ssl_cert", "ssl_key", "ssl_verify_cert", "ssl_verify_identity",
                                   "tls_versions", "tls_ciphersuites", "dns_srv", "failover")):
            raise registry._error("unsupported_options", "Use explicit local TCP test settings.", driver="mysql.connector")

        def redirected(info):
            kw.update({key: info[key] for key in ("host", "port", "user", "password")})
            return original_connect(connection, **kw)

        mode = "mysql.connector." + type(connection).__name__
        return registry._connect(connection, redirected, connection.close, mode)

    registry._patch(abstract, "connect", connect)
    registry._patch(driver, "connect", factory)


def _normalize_mysqldb_args(args, kw):
    merged = dict(kw)
    if "db" in merged:
        merged["database"] = merged.pop("db")
    if "passwd" in merged:
        merged["password"] = merged.pop("passwd")
    conflict = len(args) > len(_MYSQLDB_POS_ARGS)
    for key, value in zip(_MYSQLDB_POS_ARGS, args):
        if key in merged:
            conflict = True
        else:
            merged[key] = value
    return merged, conflict


def _mysqldb(registry):
    driver = _load(registry, "mysqlclient", "MySQLdb", MYSQLCLIENT_RANGE)
    spec = MYSQLCLIENT_RANGE[2]
    try:
        connections_mod = importlib.import_module("MySQLdb.connections")
    except (ImportError, AttributeError, OSError) as error:
        raise registry._error(
            "driver_unavailable",
            "Inspect the driver import cause or use explicit child configuration.",
            driver="MySQLdb",
        ) from error
    cls = getattr(connections_mod, "Connection", None)
    prog_err = getattr(driver, "ProgrammingError", None)
    if not isinstance(cls, type) or not isinstance(prog_err, type):
        raise registry._error(
            "unsupported_driver_version",
            f"Installed mysqlclient lacks expected Connection/ProgrammingError classes; use mysqlclient{spec} or explicit child configuration.",
            driver="MySQLdb",
        )
    original_init = _require_callable(registry, cls, "__init__", package="mysqlclient", spec=spec, driver="MySQLdb")
    _require_callable(registry, cls, "close", package="mysqlclient", spec=spec, driver="MySQLdb")

    def initialize(connection, *args, **kw):
        merged, conflict = _normalize_mysqldb_args(args, kw)
        if conflict:
            return original_init(connection, *args, **kw)
        if not _selected(registry, connection, merged.get("host"), merged.get("port"), merged.get("database")):
            return original_init(connection, *args, **kw)
        if merged.get("read_default_file") or merged.get("read_default_group"):
            raise registry._error("option_file", "Resolve this profile to explicit test settings.", driver="MySQLdb")
        if merged.get("unix_socket") or merged.get("named_pipe"):
            raise registry._error("transport_conflict", "Use the registered TCP profile explicitly.", driver="MySQLdb")
        ssl_mode = merged.get("ssl_mode")
        if ssl_mode is not None and ssl_mode not in ("DISABLED", "PREFERRED"):
            raise registry._error("tls_unavailable", "This child has no TLS; select an explicit local test profile.", driver="MySQLdb")
        ssl = merged.get("ssl")
        if ssl is not None and ssl is not False and ssl_mode != "DISABLED":
            raise registry._error("tls_unavailable", "This child has no TLS; select an explicit local test profile.", driver="MySQLdb")
        if (
            merged.get("compress")
            or merged.get("local_infile")
            or merged.get("local_infile_dir")
            or merged.get("server_public_key_path")
            or merged.get("auth_plugin")
        ):
            raise registry._error("unsupported_options", "Use explicit local TCP test settings.", driver="MySQLdb")

        def close():
            if not getattr(connection, "open", False):
                return
            try:
                connection.close()
            except prog_err as error:
                if "closing a closed connection" not in str(error):
                    raise

        def redirected(info):
            rewritten = dict(merged)
            rewritten.update(
                host=info["host"],
                port=info["port"],
                user=info["user"],
                password=info["password"],
            )
            return original_init(connection, **rewritten)

        return registry._connect(connection, redirected, close, "MySQLdb")

    registry._patch(cls, "__init__", initialize)
