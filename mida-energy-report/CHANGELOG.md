# Changelog

All notable changes to the Energy Reports add-on will be documented in this file.

## [2.0.1] - 2026-01-02

### Changed
- Default automatic report generation set to "Never" instead of "Daily"
- GitHub repository link moved to addon store page instead of UI header
- Simplified automatic report generation configuration (single dropdown)
- Removed checkbox for enabling automatic updates

### Fixed
- Default configuration now correctly shows "Never" for automatic report generation
- UI centered "Generate Report" button with auto-width sizing

## [2.0.0] - 2026-01-02

### Added
- Completely redesigned UI to match Home Assistant design language
- One-button report generation workflow (collects data + generates report)
- Reports History section with view, download, and delete capabilities
- Auto-update configuration integrated into main Configuration card
- Automatic report generation at configurable intervals (hourly to weekly)
- Background worker thread for scheduled report generation
- PDF files now include timestamps in filename for better organization
- Material Design icons and color scheme matching Home Assistant
- Smooth transitions and hover effects throughout UI
- Persistent storage using `/share` directory for container restarts

### Changed
- Streamlined UI: merged device selection and report generation into single card
- Removed separate "Collect Data" and "Generate Report" buttons
- Configuration card now includes time range and auto-update settings
- Reports History moved next to device selection for better workflow
- Button styling updated with proper icon centering and Home Assistant colors
- Header with gradient background (blue theme)
- Improved card shadows, borders, and spacing
- Device items with better hover states and visual feedback
- Download and delete buttons with perfect icon alignment
- Status messages with color-coded backgrounds (success/error/info)

### Fixed
- Device filtering bug - now correctly generates reports only for selected devices
- CSV file path issues - now correctly saves to `/share/energy_reports/data`
- PDF naming with dots in entity_ids converted to underscores
- Duplicate report generation issues resolved
- Button icon centering perfected across all buttons
- Auto-update configuration now fully functional with background worker
- Reports auto-refresh after generation

## [1.2.0] - 2025-01-XX

### Added
- Home Assistant history API integration for efficient data retrieval
- Device selection UI with checkboxes for custom reports
- All device data now collected automatically from HA history
- Device selection affects only report generation, not data collection
- Fetches last 7 days of historical data from Home Assistant

### Changed
- Disabled background polling in favor of on-demand history fetch
- Improved data collection to fetch from ALL discovered Shelly devices
- Device selection now only filters which devices appear in reports
- Updated UI messages to clarify new data collection approach
- More efficient data retrieval using HA's built-in history database

### Fixed
- Improved performance by eliminating continuous polling
- Reduced load on Home Assistant by using history API
- Better data consistency using HA's stored historical data

## [1.1.0] - 2025-01-XX

### Added
- Home Assistant Ingress integration for sidebar UI
- Material Design dark theme matching Home Assistant
- Device selection interface with entity management
- API endpoints for entity discovery and selection

### Changed
- Removed all emoji characters from codebase
- Separated temporary files from final PDF outputs
- Improved JSON response handling

### Fixed
- JSON parsing errors in API responses
- Download button state management
- Multi-worker initialization conflicts

## [1.0.6] - 2025-12-31

### Added
- Automatic Shelly device discovery from Home Assistant
- Background data collection with configurable intervals
- Manual data collection button in web interface
- Reports now saved to `/media/energy_reports` for easy access
- Enhanced web UI with detailed status messages
- Comprehensive logging with visual indicators
- Direct download link appears after report generation

### Changed
- Renamed from "Mida Energy Report Generator" to "Energy Reports"
- Changed default paths to use `energy_reports` naming
- Migrated to Alpine-based image for better performance
- Improved permissions handling for container execution
- Updated panel icon to chart-line for better representation

### Fixed
- Fixed permission denied errors on entrypoint execution
- Resolved AppArmor conflicts with init system
- Corrected CSV file path handling

## [1.0.5] - 2025-12-30

### Initial Release
- First version of the add-on
- Basic PDF report generation
- Manual CSV data processing
- Flask-based web interface

---

## Future Plans

- [ ] Multiple report templates
- [ ] Email report delivery
- [ ] Historical data comparison
- [ ] Cost calculation features
- [ ] Multi-language support
- [ ] Custom date range selection
- [ ] Export to other formats (Excel, JSON)
