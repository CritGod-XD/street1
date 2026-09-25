# StreetLens

### Pavement Condition Monitoring & Roadway Analysis Platform

StreetLens is a web-based pavement condition monitoring platform designed to visualize, analyze, and present roadway condition data using pavement imagery, Pavement Condition Index (PCI) scores, distress measurements, and geographic information.

The platform combines structured pavement-condition data with OpenStreetMap (OSM) road geometry to provide an interactive map-based view of roadway conditions.

---

## Overview

StreetLens provides a centralized dashboard for viewing pavement condition across evaluated road segments.

The system currently focuses on roadways in **Collingswood, New Jersey**, with the architecture designed so that additional locations and larger datasets can be integrated later.

The main goals of StreetLens are:

- Visualize pavement conditions geographically.
- Display PCI and distress information for individual road segments.
- Connect spreadsheet-based pavement data with actual road geometries.
- Display analyzed pavement images alongside geographic information.
- Provide an interactive and presentation-friendly dashboard.
- Prepare the system for future integration with a backend API and larger datasets.

---

# Features

## Interactive Road Map

StreetLens uses an interactive MapLibre-based map to display evaluated road segments.

The map supports:

- Road-condition overlays
- Zoom and pan
- Satellite imagery
- Road labels
- Road selection
- Information popups
- Map reset
- Expanded map view
- Fullscreen map mode

Road segments are displayed using condition-based colors so that roadway condition can be understood visually.

---

## PCI Visualization

Pavement Condition Index (PCI) data is used as one of the primary indicators of pavement condition.

Each evaluated road can contain information such as:

- Road name
- PCI score
- Overall distress score
- Distress categories
- Road location
- Related pavement imagery

PCI values are connected to geographic road segments and displayed on the interactive map.

---

# System Architecture

The current system follows this general architecture:

```text
                 ┌──────────────────────┐
                 │   PCI Spreadsheet    │
                 │  Road + PCI Data     │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ PCI Processing /     │
                 │ Matching Script      │
                 └──────────┬───────────┘
                            │
                            │ Road Names
                            ▼
                 ┌──────────────────────┐
                 │ OpenStreetMap /      │
                 │ Overpass API         │
                 └──────────┬───────────┘
                            │
                            │ Road Geometry
                            ▼
                 ┌──────────────────────┐
                 │ GeoJSON Generation   │
                 │ + PCI Matching       │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ StreetLens Dashboard │
                 │ Flask + Jinja        │
                 └──────────┬───────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        Interactive     Pavement       Analytics
           Map           Images         / Details
