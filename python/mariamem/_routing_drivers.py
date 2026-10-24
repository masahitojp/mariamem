"""Version-bound driver hooks; imported only by explicit routing.install()."""
import importlib
import importlib.metadata


def _load(registry, package, module, version):
    try:
        actual = importlib.metadata.version(package)
        if actual != version:
            raise registry._error("unsupported_driver_version",
                                  "Use the tested driver version or explicit child configuration.", driver=module)
        return importlib.import_module(module)
    except (ImportError, AttributeError, OSError) as error:
        raise registry._error("driver_unavailable", "Inspect the driver import cause or use explicit child configuration.", driver=module) from error


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
    else:
        raise registry._error("unsupported_driver", "Select pymysql or mysql.connector, or use explicit configuration.", driver=name)


def _pymysql(registry):
    driver = _load(registry, "PyMySQL", "pymysql", "1.2.3")
    cls = driver.connections.Connection
    original_init, original_connect = cls.__init__, cls.connect

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
        if connection._ssl_required:
            raise registry._error("tls_unavailable", "This child has no TLS; select an explicit local test profile.", driver="pymysql")

        def close():
            try:
                connection.close()
            except driver.err.Error as error:
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
    driver = _load(registry, "mysql-connector-python", "mysql.connector", "26.7.0")
    abstract = importlib.import_module("mysql.connector.abstracts").MySQLConnectionAbstract
    original_connect, original_factory = abstract.connect, driver.connect

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
