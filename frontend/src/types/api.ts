export type Projection = 'pca' | 'umap'
export interface Point { id: number; word: string; category?: string; positions: Record<Projection, [number, number, number]> }
export interface DatasetSummary { dataset_id: string; model_name: string; data_kind: 'synthetic' | 'pretrained'; point_count: number; embedding_dimensions: number }
export interface Diagnostic { value: number; n_neighbors: number; input_metric: string; output_metric: string; sample_count: number }
export interface Metadata extends DatasetSummary { source_url: string; license_note: string; diagnostics: { pca_explained_variance_ratio: number[]; pca_explained_variance_total: number; trustworthiness: Record<Projection, Diagnostic> }; projection_params: Record<Projection, Record<string, unknown>> }
export interface Comparison { dataset_id: string; metric: string; space: string; words: string[]; matrix: number[][] }
export interface RankedWord { id: number; word: string; score: number }
export interface Ranking { dataset_id: string; candidate_scope: string; candidate_count: number; requested_k: number; returned_count: number; results: RankedWord[]; space: string }
