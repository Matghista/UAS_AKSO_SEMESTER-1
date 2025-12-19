from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from contextlib import contextmanager

app = FastAPI(title="Product Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'products'),
    'user': os.getenv('DB_USER', 'productuser'),
    'password': os.getenv('DB_PASSWORD', 'productpass')
}

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

class Mahasiswa(BaseModel):
    nim: str
    nama: str
    jurusan: str
    angkatan: int = Field(ge=0)

# Database connection pool
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.on_event("startup")
async def startup_event():
    try:
        with get_db_connection() as conn:
            print("Acad Service: Connected to PostgreSQL")
    except Exception as e:
        print(f"Acad Service: PostgreSQL connection error: {e}")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "Acad Service is running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/acad/mahasiswa")
async def get_mahasiswas():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM mahasiswa"

            cursor.execute(query)
            rows = cursor.fetchall()

            return [{"nim": row[0], "nama": row[1], "jurusan": row[2], "angkatan": row[3]} for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
#TAMBAHAN CONVERT_GRADE_TO_WEIGHT
#START
def convert_grade_to_weight(nilai_huruf: str) -> float:
    """Mengkonversi nilai huruf menjadi bobot angka sesuai standar IPS."""
    grade_map = {
        'A': 4.0, 'B+': 3.5, 'B': 3.0, 'B-': 2.75,
        'C+': 2.5, 'C': 2.0, 'D': 1.0, 'E': 0.0
    }
    return grade_map.get(nilai_huruf.upper(), 0.0)
#END
    
@app.get("/api/acad/ips")
async def calculate_ips(nim: str = Query(..., description="NIM Mahasiswa", min_length=5)):
    try:
        with get_db_connection() as conn:
            # Menggunakan RealDictCursor agar hasil query berupa dictionary
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Query untuk mengambil nilai dan SKS mahasiswa tertentu
            query = """
            SELECT 
                m.nim,
                m.nama,
                m.jurusan,
                krs.nilai, 
                mk.sks
            FROM mahasiswa m 
            JOIN krs ON krs.nim = m.nim 
            JOIN mata_kuliah mk ON mk.kode_mk = krs.kode_mk 
            WHERE m.nim = %s;
            """

            # Eksekusi query dengan NIM sebagai parameter
            cursor.execute(query, (nim,))
            rows = cursor.fetchall()

            if not rows:
                raise HTTPException(status_code=404, detail=f"Data KRS tidak ditemukan untuk NIM {nim}")

            # Inisialisasi variabel perhitungan
            total_bobot_sks = 0.0
            total_sks = 0
            
            # Perhitungan IPS
            for row in rows:
                nilai_huruf = row['nilai']
                sks_matkul = row['sks']
                    
                # 1.Konversi nilai huruf ke bobot angka
                bobot_nilai = convert_grade_to_weight(nilai_huruf)
                   
                # 2.Hitung (Bobot Nilai x SKS)
                bobot_sks_matkul = bobot_nilai * sks_matkul
                   
                # 3.Akumulasi total bobot SKS dan total SKS
                total_bobot_sks += bobot_sks_matkul
                total_sks += sks_matkul

            if total_sks == 0:
                ips = 0.0 # Menghindari pembagian dengan nol jika tidak ada SKS yang diambil
            else:
                # 4.Hitung IPS (Total Bobot SKS / Total SKS)
                ips = total_bobot_sks / total_sks
                
            # Ambil data mahasiswa (dari baris pertama)
            mahasiswa_info = {
                "nim": rows[0]['nim'],
                "nama": rows[0]['nama'],
                "jurusan": rows[0]['jurusan']
            }

            return {
                "mahasiswa": mahasiswa_info,
                "total_sks_diambil": total_sks,
                "total_bobot_sks": round(total_bobot_sks, 2),
                "ips": round(ips, 2) # Format IPS menjadi 2 angka di belakang koma
            }

    except HTTPException:
         # Re-raise HTTPException yang sudah didefinisikan (e.g., 404)
         raise
    except Exception as e:
        # Menangkap semua error lain (misal: database connection error)
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan server: {str(e)}")