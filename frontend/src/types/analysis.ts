/**
 * Shape of an analysis result (backend frontend schema v1.0.0,
 * pipeline/frontend_schema.py) as consumed by the UI.
 */

export interface DimensionsParsed {
  width_ft: number;
  width_in: number;
  height_ft: number;
  height_in: number;
  width_total_inches?: number;
  height_total_inches?: number;
  area_sqft: number;
}

export interface RoomArea {
  value_sqft: number | null;
  source: string;
  raw_text?: string | null;
}

export interface RoomConfidence {
  geometry: number;
  label: number;
  dimensions: number;
}

export interface RoomGeometry {
  centroid: { x: number; y: number };
  bbox: { x1: number; y1: number; x2: number; y2: number };
  polygon: number[][];
  area_pixels: number;
}

export interface Room {
  id: number;
  label: string | null;
  label_raw?: string | null;
  dimensions: string | null;
  dimensions_parsed: DimensionsParsed | null;
  area?: RoomArea | null;
  confidence: RoomConfidence;
  geometry: RoomGeometry;
  color?: string;
}

export interface ResultPage {
  page_index?: number;
  image_path?: string;
  overlay_path?: string;
  image_dimensions?: { width: number; height: number };
  rooms: Room[];
}

export interface PageImage {
  page: number;
  url: string;
}

export interface ResultJson {
  schema_version?: string;
  pages?: ResultPage[];
  /** Legacy single-image format: rooms at the top level */
  rooms?: Room[];
  extracted_images?: PageImage[];
  overlay_images?: PageImage[];
  color_legend?: { label: string; color: string }[];
}
