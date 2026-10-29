# Local OCR research

Research snapshot: 28 October 2026. No candidates were benchmarked on this project's documents, so the recommendations are starting points, not measured winners.

## Recommendation

For printed English reports, evaluate **PP-OCRv6 through RapidOCR with ONNX Runtime**, starting with its small model and comparing medium against the existing installed `rapidocr-onnxruntime` baseline. This retains a local OCR approach while testing a newer model; current RapidOCR is a separate package/API and should not be assumed to be a drop-in upgrade. Paddle reports its own benchmark improvements on general/internal data, not on our lab sheets. [PaddleOCR PP-OCRv6](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv6/PP-OCRv6.en.md), [RapidOCR model list](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/model_list.md).

For Bengali and mixed Bengali/English, benchmark **EasyOCR** alongside **Tesseract**: EasyOCR's source explicitly allows `bn` plus `en`; Tesseract publishes `ben` and `eng` data. PP-OCRv6's documented 50-language model covers English, Chinese, Japanese and Latin-script languages, not Bengali; do not assume it handles Bangla. [EasyOCR language selection](https://github.com/JaidedAI/EasyOCR/blob/master/easyocr/easyocr.py), [Tesseract data](https://github.com/tesseract-ocr/tessdoc/blob/main/Data-Files.md), [PaddleOCR project](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/index.en.md).

For printed tabular extraction, test **PP-StructureV3** separately if preserving table rows and columns is required. It includes a table recognition pipeline but is a larger integration than simple text OCR. [PaddleOCR documentation](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html).

Handwritten prescriptions remain unproven: none of these sources establish reliable recognition of local doctors' handwriting, drug names, or doses. Treat all such output as draft transcription requiring source-image review, and do not infer missing text.

## Project implications

The current local OCR is used to find identifier text boxes, not to populate lab records. `identifier_boxes` matches English labels and selected patterns in individual text boxes; even perfect recognition can miss an adjacent value or an unlabeled name. Simply swapping models cannot guarantee redaction. A safer workflow needs conservative region selection, manual correction/confirmation and tests for missed identifiers. The overlay is not itself a safely redacted image.

SAM segmentation and OCR solve different problems. Current default SAM sends the original image to Meta before OCR redaction; selecting local OCR alone does not make ingestion fully local. Local SAM requires its own checkpoint.

## Evaluation before selection

Use consented or synthetic, annotated report photos representative of lighting, skew, English/Bengali, layouts and handwriting. Keep identifiable images local. Split by document template and measure: identifier-box recall and whether the entire identifier is covered; exact matching of numeric values, units, ranges, drug names and dose strings; row/column association; latency and peak memory on the actual deployment machine. Include character/word error rate as secondary metrics. Compare current RapidOCR against PP-OCRv6, and EasyOCR/Tesseract for Bengali. Explicitly record model version, weights, runtime, hardware and offline behavior. Never infer real-world performance from the three fictional samples alone.
