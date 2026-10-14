def classFactory(iface):
    """invoke plugin"""
    from .qgis_studio_themes import QgisStudioThemesPlugin  # pylint: disable=import-outside-toplevel

    return QgisStudioThemesPlugin(iface)
    
