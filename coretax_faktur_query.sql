-- Query Coretax Faktur Keluaran (dari coretax_faktur_gui.py)
-- Periode contoh: 2026-10-01 s/d 2026-10-31 -> ganti tanggal di CTE header sesuai kebutuhan.

-- =====================================================================
-- 0. CEK KOLOM OPSIONAL (dipakai app untuk memilih versi query Faktur)
-- =====================================================================
SELECT table_name, column_name FROM information_schema.columns
WHERE table_name IN ('cardfile', 'emails')
  AND column_name IN ('identity_type', 'country_code', 'tku_id', 'value', 'data_id');


-- =====================================================================
-- 1a. FAKTUR - server yang PUNYA kolom identity_type, country_code, tku_id & tabel emails
-- =====================================================================
WITH header AS (
    SELECT j.id, j.tanggal, j.nojurnal, j.contact_id,
           ROW_NUMBER() OVER (ORDER BY j.tanggal, j.nojurnal, j.id) AS baris
    FROM public.g_jurnal j
    WHERE j.tanggal BETWEEN '2026-10-01' AND '2026-10-31'
      AND j.kelompok = 4
      AND EXISTS (SELECT 1 FROM sales s WHERE s.transaction_id = j.id)
)
SELECT h.baris AS "BARIS", TO_CHAR(h.tanggal, 'MM/DD/YYYY') AS "Tanggal Faktur",
    'Normal' AS "Jenis Faktur", s.coretax_transaction_code AS "Kode Transaksi",
    '' AS "Keterangan Tambahan", '' AS "Dokumen Pendukung", '' AS "Period Dok Pendukung",
    h.nojurnal AS "Referensi", '' AS "Cap Fasilitas", '' AS "ID TKU Penjual",
    c.tax_id_number AS "NPWP/NIK Pembeli", c.identity_type AS "Jenis ID Pembeli",
    c.country_code AS "Negara Pembeli", '' AS "Nomor Dokumen", c.perusahaan AS "Nama Pembeli",
    a.complete_address AS "Alamat Pembeli", e.value AS "Email Pembeli",
    c.tku_id AS "ID TKU Pembeli"
FROM header h
JOIN sales s ON s.transaction_id = h.id
LEFT JOIN cardfile c ON c.contact_id = h.contact_id
LEFT JOIN LATERAL (SELECT complete_address FROM addresses
                   WHERE data_id = c.contact_id AND type = 'billing' LIMIT 1) a ON TRUE
LEFT JOIN LATERAL (SELECT value FROM emails WHERE data_id = c.contact_id LIMIT 1) e ON TRUE
ORDER BY h.baris;


-- =====================================================================
-- 1b. FAKTUR - server TANPA kolom tersebut (nilai pengganti)
--     Kode Transaksi = NULL (app isi default form, mis. 04), Jenis ID = TIN, Negara = IDN, Email = '', ID TKU = NPWP 16 digit + 000000
--     (bila hanya sebagian kolom yang tidak ada, app mengganti kolom itu saja)
-- =====================================================================
WITH header AS (
    SELECT j.id, j.tanggal, j.nojurnal, j.contact_id,
           ROW_NUMBER() OVER (ORDER BY j.tanggal, j.nojurnal, j.id) AS baris
    FROM public.g_jurnal j
    WHERE j.tanggal BETWEEN '2026-10-01' AND '2026-10-31'
      AND j.kelompok = 4
      AND EXISTS (SELECT 1 FROM sales s WHERE s.transaction_id = j.id)
)
SELECT h.baris AS "BARIS", TO_CHAR(h.tanggal, 'MM/DD/YYYY') AS "Tanggal Faktur",
    'Normal' AS "Jenis Faktur", NULL AS "Kode Transaksi",
    '' AS "Keterangan Tambahan", '' AS "Dokumen Pendukung", '' AS "Period Dok Pendukung",
    h.nojurnal AS "Referensi", '' AS "Cap Fasilitas", '' AS "ID TKU Penjual",
    c.tax_id_number AS "NPWP/NIK Pembeli", 'TIN' AS "Jenis ID Pembeli",
    'IDN' AS "Negara Pembeli", '' AS "Nomor Dokumen", c.perusahaan AS "Nama Pembeli",
    a.complete_address AS "Alamat Pembeli", '' AS "Email Pembeli",
    NULLIF(CASE WHEN LENGTH(REGEXP_REPLACE(COALESCE(c.tax_id_number, ''), '[^0-9]', '', 'g')) = 15 THEN '0' ELSE '' END || REGEXP_REPLACE(COALESCE(c.tax_id_number, ''), '[^0-9]', '', 'g'), '') || '000000' AS "ID TKU Pembeli"
FROM header h
JOIN sales s ON s.transaction_id = h.id
LEFT JOIN cardfile c ON c.contact_id = h.contact_id
LEFT JOIN LATERAL (SELECT complete_address FROM addresses
                   WHERE data_id = c.contact_id AND type = 'billing' LIMIT 1) a ON TRUE
ORDER BY h.baris;


-- =====================================================================
-- 2. DETAIL FAKTUR
-- =====================================================================
WITH header AS (
    SELECT j.id, j.tanggal, j.nojurnal, j.contact_id,
           ROW_NUMBER() OVER (ORDER BY j.tanggal, j.nojurnal, j.id) AS baris
    FROM public.g_jurnal j
    WHERE j.tanggal BETWEEN '2026-10-01' AND '2026-10-31'
      AND j.kelompok = 4
      AND EXISTS (SELECT 1 FROM sales s WHERE s.transaction_id = j.id)
)
SELECT h.baris AS "Baris",
    CASE WHEN i.product_id IS NOT NULL THEN 'A' ELSE 'B' END AS "Barang/Jasa",
    '' AS "Kode Barang Jasa", inv.deskripsi AS "Nama Barang Jasa",
    'UM.0033' AS "Nama Satuan Ukur", i.harga AS "Harga Satuan", i.jumlah AS "Jumlah Barang Jasa",
    COALESCE(i.discount, 0) AS "Total Diskon",
    ROUND((i.jumlah * i.harga)::numeric, 2) AS "DPP",
    ROUND((i.jumlah * i.harga / 12 * 11)::numeric, 2) AS "DPP Nilai Lain",
    12 AS "Tarif PPN",
    ROUND((i.jumlah * i.harga / 12 * 11 * 0.12)::numeric, 2) AS "PPN",
    0 AS "Tarif PPnBM", 0 AS "PPnBM"
FROM header h
JOIN itemsale i ON i.transaction_id = h.id
LEFT JOIN inventor inv ON inv.id = i.product_id
ORDER BY h.baris, i.id;
