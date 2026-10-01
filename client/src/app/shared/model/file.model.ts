export interface OrionFile {
    id: string;
    public_id: string;

    original_filename: string;
    original_size: number;
    content_type: string;

    status: 'available' | 'deleted' | 'unavailable';

    created_at: string;
}

export interface OrionLinkedFile extends OrionFile {
    key: string;
    secure_url: string;
}

export interface PublicFileMetadata {
    public_id: string;

    original_filename: string;
    original_size: number;
    encrypted_size: number;

    content_type: string;

    iv: string;

    encryption_algorithm: string;
    encryption_version: number;

    provider_direct_url: string;

    content_url: string;
}
