# src/npags/gui/widgets/map_widget.py
"""
Widget de mapa GPS interativo usando Leaflet.js e OpenStreetMap.

Exibe trajetória e posição atual em tempo real com:
    - Marcador de início (verde)
    - Marcador atual com animação de pulso (vermelho)
    - Linha de trajetória
    - Painel de informações (pontos + distância)
    - Suporte a histórico e tempo real

Exemplo de uso:
    >>> from npags.gui.widgets import MapWidget
    >>>
    >>> map_widget = MapWidget(lat_key='latitude', lon_key='longitude')
    >>> map_widget.update_from_buffer(data_buffer, force_update=True)
"""

from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from npags.gui.translations import tr
from npags.gui.styles import THEME_COLORS

# WebEngine é opcional
HAS_WEBENGINE = False
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None


class _MapWidgetFallback(QWidget):
    """
    Widget de fallback quando PyQt6-WebEngine não está disponível.
    Exibe coordenadas em texto.
    """

    def __init__(
        self,
        lat_key: str = 'latitude',
        lon_key: str = 'longitude',
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.lat_key = lat_key
        self.lon_key = lon_key
        self.trajectory: list[list[float]] = []
        self.current_position: list[float] | None = None
        self._is_destroyed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self._title = QLabel("🗺️ Mapa GPS")
        self._title.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-size: 14px; font-weight: bold;")
        layout.addWidget(self._title)

        self._info = QLabel("PyQt6-WebEngine não instalado.\nInstale com: pip install PyQt6-WebEngine")
        self._info.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 11px;")
        layout.addWidget(self._info)

        self._coords = QLabel(tr("Aguardando coordenadas..."))
        self._coords.setStyleSheet(f"color: {THEME_COLORS['text']}; font-size: 12px; font-family: monospace;")
        layout.addWidget(self._coords)

        layout.addStretch()

    def update_from_buffer(self, data_buffer: dict[str, list[Any]], force_update: bool = False) -> None:
        lats = data_buffer.get(self.lat_key, [])
        lons = data_buffer.get(self.lon_key, [])

        if lats and lons:
            lat = lats[-1] if lats else 0
            lon = lons[-1] if lons else 0
            self.current_position = [lat, lon]
            self._coords.setText(f"Lat: {lat:.6f}\nLon: {lon:.6f}\nPontos: {len(lats)}")

    def cleanup(self) -> None:
        self._is_destroyed = True

    def clear(self) -> None:
        self.trajectory = []
        self.current_position = None
        self._coords.setText(tr("Aguardando coordenadas..."))


def _create_webengine_map_class():
    """Cria a classe MapWidget com WebEngine apenas se disponível."""
    if not HAS_WEBENGINE:
        return None

    class _MapWidgetWebEngine(QWebEngineView):
        """
        Widget de mapa GPS real usando Leaflet.js e OpenStreetMap.
        """

        def __init__(
            self,
            lat_key: str = 'latitude',
            lon_key: str = 'longitude',
            parent: QWidget | None = None
        ) -> None:
            super().__init__(parent)
            self.lat_key = lat_key
            self.lon_key = lon_key
            self._is_destroyed = False
            self._map_ready = False
            self._pending_update: tuple | None = None
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

            # Configuração de cores do tema
            self.accent_color = THEME_COLORS.get('accent', '#ae5516')
            self.bg_color = THEME_COLORS.get('background', '#1a1a1a')

            # Conecta sinal de carregamento completo
            self.loadFinished.connect(self._on_load_finished)

            # HTML do mapa com Leaflet.js
            self.map_html = self._create_map_html()
            self.setHtml(self.map_html)

            # Lista de coordenadas para a trajetória
            self.trajectory: list[list[float]] = []
            self.current_position: list[float] | None = None

        def _on_load_finished(self, ok: bool) -> None:
            if ok:
                self._map_ready = True
                if self._pending_update:
                    self._execute_update(*self._pending_update)
                    self._pending_update = None

        def _create_map_html(self) -> str:
            return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; background: {self.bg_color}; }}
        #map {{ width: 100%; height: 100vh; }}
        .coord-label {{
            background: rgba(0, 0, 0, 0.7); color: white;
            padding: 5px 10px; border-radius: 4px;
            font-family: monospace; font-size: 12px;
            border: 1px solid {self.accent_color};
        }}
        .leaflet-container {{ background: #1a1a1a; }}
        @keyframes pulse {{
            0% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.2); opacity: 0.8; }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}
        .current-marker div {{ animation: pulse 1.5s ease-in-out infinite; }}
        .distance-info {{
            position: absolute; bottom: 10px; left: 10px;
            background: rgba(0, 0, 0, 0.7); color: white;
            padding: 8px 12px; border-radius: 4px;
            font-family: monospace; font-size: 11px;
            z-index: 1000; border: 1px solid {self.accent_color};
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([-15.7801, -47.9292], 4);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '© OpenStreetMap contributors © CARTO', maxZoom: 19
        }}).addTo(map);

        var trajectoryLayer = L.layerGroup().addTo(map);
        var pathLine = null, currentMarker = null, hasFittedBounds = false;

        function updateMap(trajectory, currentPos, fitBounds) {{
            if (typeof placeholderMarker !== 'undefined' && placeholderMarker) {{
                map.removeLayer(placeholderMarker); placeholderMarker = null;
            }}
            trajectoryLayer.clearLayers();

            if (trajectory && trajectory.length > 0) {{
                pathLine = L.polyline(trajectory, {{
                    color: '{self.accent_color}', weight: 3, opacity: 0.8
                }}).addTo(trajectoryLayer);

                if (trajectory.length > 1) {{
                    var startIcon = L.divIcon({{
                        className: 'start-marker',
                        html: '<div style="background-color: #32cd32; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white;"></div>',
                        iconSize: [14, 14], iconAnchor: [7, 7]
                    }});
                    L.marker(trajectory[0], {{icon: startIcon}}).addTo(trajectoryLayer);
                }}

                if (fitBounds || !hasFittedBounds) {{
                    map.fitBounds(pathLine.getBounds(), {{padding: [50, 50], maxZoom: 16}});
                    hasFittedBounds = true;
                }}
            }}

            if (currentPos) {{
                var lat = currentPos[0], lon = currentPos[1];
                if (Math.abs(lat) < 0.001 && Math.abs(lon) < 0.001) return;

                var customIcon = L.divIcon({{
                    className: 'current-marker',
                    html: '<div style="background-color: #ff3232; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white;"></div>',
                    iconSize: [20, 20], iconAnchor: [10, 10]
                }});

                currentMarker = L.marker([lat, lon], {{icon: customIcon}})
                    .bindPopup('<div class="coord-label"><strong>Posição Atual</strong><br>Lat: ' + lat.toFixed(6) + '<br>Lon: ' + lon.toFixed(6) + '</div>')
                    .addTo(trajectoryLayer);

                if (!trajectory || trajectory.length === 0) {{
                    map.setView([lat, lon], 15); hasFittedBounds = true;
                }} else if (!fitBounds && hasFittedBounds) {{
                    map.panTo([lat, lon], {{animate: true, duration: 0.5}});
                }}
            }}

            var infoEl = document.getElementById('trajectory-info');
            if (infoEl && trajectory && trajectory.length > 0) {{
                var dist = 0;
                for (var i = 1; i < trajectory.length; i++) {{
                    var lat1 = trajectory[i-1][0] * Math.PI / 180;
                    var lat2 = trajectory[i][0] * Math.PI / 180;
                    var dLat = lat2 - lat1;
                    var dLon = (trajectory[i][1] - trajectory[i-1][1]) * Math.PI / 180;
                    var a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon/2) * Math.sin(dLon/2);
                    dist += 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
                }}
                var distStr = dist > 1000 ? (dist/1000).toFixed(2) + ' km' : dist.toFixed(0) + ' m';
                infoEl.innerHTML = '<b>Pontos:</b> ' + trajectory.length + '<br><b>Distancia:</b> ' + distStr;
            }}
        }}

        var placeholderMarker = L.marker([-15.7801, -47.9292])
            .bindPopup('<div class="coord-label">Aguardando sinal GPS...</div>')
            .addTo(map).openPopup();

        var infoDiv = L.control({{position: 'bottomleft'}});
        infoDiv.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'distance-info');
            div.id = 'trajectory-info';
            div.innerHTML = tr('Aguardando dados...');
            return div;
        }};
        infoDiv.addTo(map);
    </script>
</body>
</html>
"""

        def update_from_buffer(self, data_buffer: dict[str, list[Any]], force_update: bool = False) -> None:
            lats = data_buffer.get(self.lat_key, [])
            lons = data_buffer.get(self.lon_key, [])

            if not lats or not lons:
                return

            min_len = min(len(lats), len(lons))
            if min_len == 0:
                return

            max_points = 1000
            start_idx = max(0, min_len - max_points)

            trajectory: list[list[float]] = []
            for i in range(start_idx, min_len):
                try:
                    lat = float(lats[i])
                    lon = float(lons[i])
                    if abs(lat) < 0.001 and abs(lon) < 0.001:
                        continue
                    trajectory.append([lat, lon])
                except (ValueError, TypeError):
                    continue

            if not force_update and trajectory == self.trajectory:
                return

            self.trajectory = trajectory
            current_pos: list[float] | None = trajectory[-1] if trajectory else None
            self.current_position = current_pos

            trajectory_json = json.dumps(trajectory)
            current_json = json.dumps(current_pos)

            if self._is_destroyed:
                return

            fit_bounds = len(trajectory) > 10 or force_update

            if not self._map_ready:
                self._pending_update = (trajectory_json, current_json, fit_bounds)
                return

            self._execute_update(trajectory_json, current_json, fit_bounds)

        def _execute_update(self, trajectory_json: str, current_json: str, fit_bounds: bool) -> None:
            if self._is_destroyed:
                return
            js_code = f"if (typeof updateMap === 'function') {{ updateMap({trajectory_json}, {current_json}, {str(fit_bounds).lower()}); }}"
            try:
                self.page().runJavaScript(js_code)
            except RuntimeError:
                self._is_destroyed = True

        def cleanup(self) -> None:
            self._is_destroyed = True
            try:
                self.setHtml('')
                self.page().deleteLater()
            except Exception:
                pass  # Erro de parsing/runtime ignorado

        def clear(self) -> None:
            self.trajectory = []
            self.current_position = None
            if self._map_ready:
                self._execute_update('[]', 'null', True)

    return _MapWidgetWebEngine


# Cria a classe WebEngine se disponível
_MapWidgetWebEngine = _create_webengine_map_class()


def MapWidget(
    lat_key: str = 'latitude',
    lon_key: str = 'longitude',
    parent: QWidget | None = None
) -> _MapWidgetFallback | Any:
    """
    Cria um widget de mapa GPS.

    Se PyQt6-WebEngine estiver disponível, usa mapa interativo com Leaflet.js.
    Caso contrário, usa fallback com exibição de coordenadas em texto.

    Args:
        lat_key: Nome do campo de latitude no buffer.
        lon_key: Nome do campo de longitude no buffer.
        parent: Widget pai (opcional).

    Returns:
        Widget de mapa (WebEngine ou Fallback).
    """
    if HAS_WEBENGINE and _MapWidgetWebEngine is not None:
        return _MapWidgetWebEngine(lat_key, lon_key, parent)
    else:
        return _MapWidgetFallback(lat_key, lon_key, parent)
