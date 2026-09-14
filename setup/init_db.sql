DROP TABLE IF EXISTS active_fires CASCADE;
DROP TABLE IF EXISTS industrial_zones CASCADE;
DROP TABLE IF EXISTS india_boundary CASCADE;

CREATE TABLE india_boundary (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) DEFAULT 'India',
    geom GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX idx_india_boundary_geom ON india_boundary USING GIST (geom);

CREATE TABLE industrial_zones (
    id SERIAL PRIMARY KEY,
    osm_id VARCHAR(50),
    name VARCHAR(255),
    facility_type VARCHAR(100),
    geom GEOMETRY(Geometry, 4326) NOT NULL
);
CREATE INDEX idx_industrial_zones_geom ON industrial_zones USING GIST (geom);

CREATE TABLE active_fires (
    id SERIAL PRIMARY KEY,
    firms_id VARCHAR(50),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    brightness_kelvin DOUBLE PRECISION,
    frp_mw DOUBLE PRECISION,
    confidence VARCHAR(20),
    source_type VARCHAR(50) DEFAULT 'unclassified', 
    is_industrial BOOLEAN DEFAULT FALSE,
    facility_id INT REFERENCES industrial_zones(id),
    detected_at TIMESTAMP WITH TIME ZONE,
    geom GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX idx_active_fires_geom ON active_fires USING GIST (geom);