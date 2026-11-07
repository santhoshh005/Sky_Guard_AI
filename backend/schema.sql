-- SkyGuard AI database schema (PostgreSQL / Supabase).
-- Apply once in the Supabase SQL editor. Safe to re-run: uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS stations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_code VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  elevation_m DOUBLE PRECISION,
  state VARCHAR(100),
  district VARCHAR(100),
  station_type VARCHAR(50) DEFAULT 'AWS',
  expected_interval_min INTEGER DEFAULT 15,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  observed_at TIMESTAMPTZ NOT NULL,
  temperature DOUBLE PRECISION,
  humidity DOUBLE PRECISION,
  pressure DOUBLE PRECISION,
  wind_speed DOUBLE PRECISION,
  wind_direction DOUBLE PRECISION,
  rainfall DOUBLE PRECISION,
  solar_radiation DOUBLE PRECISION,
  ingested_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(station_id, observed_at)
);

CREATE TABLE IF NOT EXISTS anomaly_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id UUID NOT NULL REFERENCES observations(id) ON DELETE CASCADE UNIQUE,
  qc_score DOUBLE PRECISION NOT NULL CHECK (qc_score >= 0 AND qc_score <= 1),
  if_score DOUBLE PRECISION NOT NULL CHECK (if_score >= 0 AND if_score <= 1),
  ae_score DOUBLE PRECISION NOT NULL CHECK (ae_score >= 0 AND ae_score <= 1),
  fused_score DOUBLE PRECISION NOT NULL CHECK (fused_score >= 0 AND fused_score <= 1),
  confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  is_anomaly BOOLEAN NOT NULL,
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('normal', 'warning', 'critical')),
  root_cause VARCHAR(30) CHECK (root_cause IN ('spike', 'frozen', 'drift', 'communication', 'multivariate')),
  explanation TEXT,
  qc_flags JSONB DEFAULT '{}',
  shap_values JSONB DEFAULT '{}',
  scored_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  anomaly_score_id UUID REFERENCES anomaly_scores(id) ON DELETE SET NULL,
  alert_type VARCHAR(30) NOT NULL CHECK (alert_type IN ('anomaly', 'health_degraded', 'maintenance_required', 'communication_loss')),
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
  title VARCHAR(500) NOT NULL,
  description TEXT,
  parameter VARCHAR(50),
  is_resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sensor_health_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  parameter VARCHAR(50) NOT NULL CHECK (parameter IN ('temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'rainfall', 'solar_radiation')),
  health_score DOUBLE PRECISION NOT NULL CHECK (health_score >= 0 AND health_score <= 100),
  status VARCHAR(30) NOT NULL CHECK (status IN ('healthy', 'degraded', 'maintenance_recommended', 'sensor_critical')),
  anomaly_streak INTEGER DEFAULT 0,
  recorded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corrected_values (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id UUID NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
  parameter VARCHAR(50) NOT NULL CHECK (parameter IN ('temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'rainfall', 'solar_radiation')),
  raw_value DOUBLE PRECISION,
  corrected_value DOUBLE PRECISION,
  correction_method VARCHAR(50) NOT NULL CHECK (correction_method IN ('temporal_median', 'interpolation', 'diurnal_trend', 'cross_parameter_regression', 'none')),
  correction_confidence DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (correction_confidence >= 0 AND correction_confidence <= 1),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(observation_id, parameter)
);



-- Indexes for the hot query paths (history lookups, dashboards, filters)
CREATE INDEX IF NOT EXISTS idx_observations_station_time ON observations (station_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_scores_scored_at ON anomaly_scores (scored_at DESC) WHERE is_anomaly;
CREATE INDEX IF NOT EXISTS idx_alerts_station_created ON alerts (station_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_open ON alerts (created_at DESC) WHERE NOT is_resolved;
CREATE INDEX IF NOT EXISTS idx_health_station_time ON sensor_health_history (station_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_corrected_observation ON corrected_values (observation_id);
