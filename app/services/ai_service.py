"""
AI Prediction Service
Handles CBC anemia predictions and blood cell image analysis
Supports CSV, Excel (XLSX, XLS), and PDF file formats
"""
import pandas as pd
import io
from typing import Dict, List, Optional, Any
import numpy as np
import cv2
from fastapi import UploadFile
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime
from pathlib import Path

# Try to import AI modules, gracefully handle if not available
try:
    from app.ai.cbc import (
        load_model_and_assets,
        prepare_dataframe_for_inference,
        build_report,
        predict_and_annotate_dataframe
    )
    CBC_AI_AVAILABLE = True
except ImportError as e:
    CBC_AI_AVAILABLE = False
    print(f"⚠️ CBC AI modules not available: {e}")

# Try to import PDF processing libraries
try:
    import pdfplumber
    import tabula
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️ PDF processing not available. Install pdfplumber and tabula-py")


# ==================== Helper Functions ====================

def detect_and_transform_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect if CSV is in vertical format (Parameter/Value) and convert to horizontal
    
    Args:
        df: Input DataFrame
        
    Returns:
        Transformed DataFrame in horizontal format
    """
    columns_lower = [str(col).strip().lower() for col in df.columns]
    
    if 'parameter' in columns_lower and 'value' in columns_lower:
        print("📋 Detected vertical format (Parameter/Value) - Converting to horizontal...")
        
        param_col = df.columns[columns_lower.index('parameter')]
        value_col = df.columns[columns_lower.index('value')]
       
        df_transposed = df.set_index(param_col)[value_col].to_frame().T
        df_transposed.reset_index(drop=True, inplace=True)
        
        df_transposed.columns = df[param_col].values
        
        return df_transposed
    
    else:
        print("📊 Detected horizontal format (standard)")
        return df


def read_excel_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Read Excel file (XLSX or XLS) and return DataFrame
    
    Args:
        file_content: Raw file bytes
        filename: Original filename
        
    Returns:
        DataFrame with the Excel data
    """
    try:
        # Try to read as Excel file
        df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
        print(f"✅ Successfully read Excel file: {filename}")
        return df
    except Exception as e:
        # If openpyxl fails, try xlrd for older .xls files
        try:
            df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
            print(f"✅ Successfully read XLS file: {filename}")
            return df
        except Exception as e2:
            raise ValueError(f"Failed to read Excel file: {str(e)}. Also tried XLS format: {str(e2)}")


def read_pdf_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Read PDF file and extract tables as DataFrame
    
    Args:
        file_content: Raw file bytes
        filename: Original filename
        
    Returns:
        DataFrame with the extracted table data
    """
    if not PDF_AVAILABLE:
        raise ImportError("PDF processing libraries not available. Install pdfplumber and tabula-py")
    
    try:
        # Method 1: Try pdfplumber first (better for structured tables)
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            all_tables = []
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table and len(table) > 0:
                            # Convert table to DataFrame
                            df = pd.DataFrame(table[1:], columns=table[0])
                            all_tables.append(df)
            
            if all_tables:
                # Combine all tables
                df = pd.concat(all_tables, ignore_index=True)
                print(f"✅ Successfully extracted table from PDF using pdfplumber: {filename}")
                return df
    except Exception as e:
        print(f"⚠️ pdfplumber failed: {e}, trying tabula...")
    
    try:
        # Method 2: Try tabula-py (better for complex PDFs)
        # Save to temporary file for tabula
        temp_path = Path(f"temp_{uuid.uuid4().hex}.pdf")
        with open(temp_path, "wb") as f:
            f.write(file_content)
        
        try:
            # Read all tables from PDF
            tables = tabula.read_pdf(str(temp_path), pages='all', multiple_tables=True)
            
            if tables and len(tables) > 0:
                # Use the first table or combine if multiple
                df = tables[0] if len(tables) == 1 else pd.concat(tables, ignore_index=True)
                print(f"✅ Successfully extracted table from PDF using tabula: {filename}")
                return df
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
    except Exception as e2:
        raise ValueError(f"Failed to extract table from PDF: {str(e2)}")
    
    raise ValueError("No tables found in PDF file")


def read_file_by_extension(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Read file based on its extension and return DataFrame
    
    Args:
        file_content: Raw file bytes
        filename: Original filename with extension
        
    Returns:
        DataFrame with the file data
    """
    file_extension = Path(filename).suffix.lower()
    
    if file_extension == '.csv':
        df = pd.read_csv(io.BytesIO(file_content))
        print(f"✅ Successfully read CSV file: {filename}")
        return df
    
    elif file_extension in ['.xlsx', '.xls']:
        return read_excel_file(file_content, filename)
    
    elif file_extension == '.pdf':
        return read_pdf_file(file_content, filename)
    
    else:
        raise ValueError(f"Unsupported file format: {file_extension}. Supported formats: CSV, XLSX, XLS, PDF")


# ==================== CBC Anemia Prediction ====================

class CBCPredictionService:
    """Service for CBC Anemia predictions"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.used_features = None
        self._loaded = False
        self._available = CBC_AI_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if AI prediction is available"""
        return self._available
    
    def load_model(self):
        """Load the model, scaler, and features"""
        if not self._available:
            raise RuntimeError("AI prediction modules are not available")
        
        if not self._loaded:
            self.model, self.scaler, self.used_features = load_model_and_assets()
            self._loaded = True
            print("✅ CBC Anemia model loaded successfully")
    
    def predict_single(self, cbc_data: Dict, with_report: bool = False) -> Dict:
        if not self._loaded:
            self.load_model()
        
        df = pd.DataFrame([cbc_data])
        df = prepare_dataframe_for_inference(df, self.used_features, self.scaler)
        
        prediction = self.model.predict(df)[0]
        probabilities = self.model.predict_proba(df)[0]
        confidence = float(max(probabilities))
        confidence_percentage = confidence * 100
        
        result = {
            "prediction": int(prediction),
            "prediction_label": "Anemia" if prediction == 1 else "Normal",
            "confidence": f"{confidence_percentage:.2f}%",
            "confidence_raw": confidence,
            "probabilities": {
                "normal": float(probabilities[0]),
                "anemia": float(probabilities[1])
            }
        }
        
        if with_report:
            result["report"] = build_report(cbc_data, prediction, confidence)
        
        return result
    
    def predict_batch(self, cbc_data_list: List[Dict], with_report: bool = False) -> List[Dict]:
        """Predict anemia for multiple CBC samples"""
        if not self._loaded:
            self.load_model()
        
        df = pd.DataFrame(cbc_data_list)
        df_prepared = prepare_dataframe_for_inference(df, self.used_features)
        
        # Extract features and scale
        X = df_prepared[self.used_features].values
        X_scaled = self.scaler.transform(X)
        
        # Make predictions
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        results = []
        for i, (pred, probs) in enumerate(zip(predictions, probabilities)):
            row_data = df_prepared.iloc[i]
            confidence_percentage = float(probs[1]) * 100
            result = {
                "row_index": i,
                "prediction": "Anemia" if int(pred) == 1 else "Normal",
                "prediction_code": int(pred),
                "probability": f"{confidence_percentage:.2f}%",
                "probability_text": f"{probs[1]:.2%}",
                "confidence": "High" if max(probs) > 0.8 else "Medium",
                "probabilities": {
                    "normal": float(probs[0]),
                    "anemia": float(probs[1])
                },
                "values": {
                    "RBC": float(row_data.get('RBC', 0)),
                    "HGB": float(row_data.get('HGB', 0)),
                    "PCV": float(row_data.get('PCV', 0)),
                    "MCV": float(row_data.get('MCV', 0)),
                    "MCH": float(row_data.get('MCH', 0)),
                    "MCHC": float(row_data.get('MCHC', 0)),
                    "TLC": float(row_data.get('TLC', 0)),
                    "PLT": float(row_data.get('PLT', 0)),
                }
            }
            
            if with_report:
                row_data_copy = row_data.copy()
                row_data_copy['Predicted_Anemia'] = pred
                row_data_copy['Anemia_Probability'] = probs[1]
                result["report"] = build_report(row_data_copy)
            
            results.append(result)
        
        return results
    
    def process_csv_upload(
        self,
        file: UploadFile,
        patient_id: int,
        uploaded_by_id: int,
        notes: str = "",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Process uploaded CBC file (CSV, Excel, or PDF)
        
        Args:
            file: Uploaded file (CSV, XLSX, XLS, or PDF)
            patient_id: Patient ID
            uploaded_by_id: ID of user uploading
            notes: Optional notes
            db: Database session
            
        Returns:
            Dict with success status and results
        """
        try:
            # Validate file
            if not file or not file.filename:
                return {
                    "success": False,
                    "message": "No file was selected. Please select a file to upload."
                }
            
            # Check file extension
            file_extension = Path(file.filename).suffix.lower()
            valid_extensions = ['.csv', '.xlsx', '.xls', '.pdf']
            
            if file_extension not in valid_extensions:
                return {
                    "success": False,
                    "message": f"Invalid file type. Please upload a file with one of these extensions: {', '.join(valid_extensions)}"
                }
            
            # Read file content
            contents = file.file.read()
            if len(contents) == 0:
                return {
                    "success": False,
                    "message": "The uploaded file is empty. Please upload a valid file with CBC data."
                }
            
            # Parse file based on extension
            try:
                df_original = read_file_by_extension(contents, file.filename)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error reading file: {str(e)}"
                }
            
            if df_original.empty:
                return {
                    "success": False,
                    "message": "The file contains no data. Please ensure your file has CBC test results."
                }
            
            # Detect and transform vertical format to horizontal
            df_original = detect_and_transform_csv(df_original)
            
            # Load model if needed
            if not self._loaded:
                self.load_model()
            
            # Make predictions
            df_annotated, probabilities = predict_and_annotate_dataframe(
                df_original, 
                self.model, 
                self.scaler, 
                self.used_features
            )
            
            if len(df_annotated) == 0:
                return {
                    "success": False,
                    "message": "No valid data rows found. Please check your file format and CBC parameter names."
                }
            
            # Prepare results for display
            results = []
            for idx, row in df_annotated.iterrows():
                prob_anemia = probabilities[idx][1] if len(probabilities) > idx else 0.5
                confidence_percentage = prob_anemia * 100
                
                result = {
                    "row_index": int(idx),
                    "prediction": row['Diagnosis'],
                    "prediction_code": int(row['Predicted_Anemia']),
                    "probability": f"{confidence_percentage:.2f}%",
                    "values": {
                        "RBC": float(row.get('RBC', 0)),
                        "HGB": float(row.get('HGB', 0)),
                        "PCV": float(row.get('PCV', 0)),
                        "MCV": float(row.get('MCV', 0)),
                        "MCH": float(row.get('MCH', 0)),
                        "MCHC": float(row.get('MCHC', 0)),
                        "TLC": float(row.get('TLC', 0)),
                        "PLT": float(row.get('PLT', 0)),
                    },
                    "report": build_report(row)
                }
                results.append(result)
            
            # Save to database
            if not db:
                return {
                    "success": False,
                    "message": "Database session is required to save test results."
                }
            
            test_id = None
            try:
                from app.database import Test, TestFile, Model
                
                # Get CBC model
                cbc_model = db.query(Model).filter(Model.name == "CBC Anemia Detection").first()
                if not cbc_model:
                    return {
                        "success": False,
                        "message": "CBC Anemia Detection model not found."
                    }
                
                # Create test record
                new_test = Test(
                    patient_id=patient_id,
                    model_id=cbc_model.id,
                    notes=notes if notes else f"CBC test uploaded via {file_extension.upper()}",
                    review_status='pending'
                )
                db.add(new_test)
                db.flush()
                test_id = new_test.id
                
                # Create uploads directory
                upload_dir = Path("uploads/tests/cbc")
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                random_id = uuid.uuid4().hex[:8]
                filename = f"cbc_{timestamp}_{random_id}.csv"
                file_path = upload_dir / filename
                
                # Save as CSV (standardized format)
                df_annotated.to_csv(file_path, index=False)
                
                # Create test_files record
                test_file = TestFile(
                    test_id=new_test.id,
                    name=filename,
                    extension='.csv',
                    path=str(file_path),
                    type='output'
                )
                db.add(test_file)
                
                # Update model test count
                cbc_model.tests_count += 1
                
                db.commit()
                
            except Exception as db_error:
                db.rollback()
                return {
                    "success": False,
                    "message": f"Error saving test to database: {str(db_error)}"
                }
            
            return {
                "success": True,
                "message": f"CBC analysis completed successfully! Analyzed {len(results)} sample(s) from {file_extension.upper()} file.",
                "results": results,
                "notes": notes,
                "patient_id": patient_id,
                "uploaded_by_id": uploaded_by_id,
                "test_id": test_id
            }
            
        except ValueError as ve:
            if db:
                db.rollback()
            return {
                "success": False,
                "message": f"File validation error: {str(ve)}"
            }
        except Exception as e:
            if db:
                db.rollback()
            return {
                "success": False,
                "message": f"Error processing file: {str(e)}"
            }
    
    def process_manual_input(
        self,
        rbc: float,
        hgb: float,
        pcv: float,
        mcv: float,
        mch: float,
        mchc: float,
        tlc: float,
        plt: float,
        patient_id: int,
        uploaded_by_id: int,
        notes: str = "",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        try:
            # Create single-row dataframe with input data
            df_input = pd.DataFrame([{
                'RBC': rbc,
                'HGB': hgb,
                'PCV': pcv,
                'MCV': mcv,
                'MCH': mch,
                'MCHC': mchc,
                'TLC': tlc,
                'PLT': plt
            }])
            
            # Load model if needed
            if not self._loaded:
                self.load_model()
            
            # Make predictions
            df_annotated, probabilities = predict_and_annotate_dataframe(
                df_input, 
                self.model, 
                self.scaler, 
                self.used_features
            )
            
            if len(df_annotated) == 0:
                return {
                    "success": False,
                    "message": "Invalid CBC values provided. Please check your input."
                }
            
            # Get the single result row
            row = df_annotated.iloc[0]
            prob_anemia = probabilities[0][1]
            confidence_percentage = prob_anemia * 100
            
            result_data = {
                "row_index": 0,
                "prediction": row['Diagnosis'],
                "prediction_code": int(row['Predicted_Anemia']),
                "probability": f"{confidence_percentage:.2f}%",
                "values": {
                    "RBC": float(row.get('RBC', 0)),
                    "HGB": float(row.get('HGB', 0)),
                    "PCV": float(row.get('PCV', 0)),
                    "MCV": float(row.get('MCV', 0)),
                    "MCH": float(row.get('MCH', 0)),
                    "MCHC": float(row.get('MCHC', 0)),
                    "TLC": float(row.get('TLC', 0)),
                    "PLT": float(row.get('PLT', 0)),
                },
                "report": build_report(row)
            }
            
            # Save to database
            if not db:
                return {
                    "success": False,
                    "message": "Database session is required to save test results."
                }
            
            test_id = None
            try:
                from app.database import Test, TestFile, Model
                
                cbc_model = db.query(Model).filter(Model.name == "CBC Anemia Detection").first()
                if not cbc_model:
                    return {
                        "success": False,
                        "message": "CBC Anemia Detection model not found."
                    }
                
                new_test = Test(
                    patient_id=patient_id,
                    model_id=cbc_model.id,
                    notes=notes if notes else "CBC test entered manually",
                    review_status='pending'
                )
                db.add(new_test)
                db.flush()
                test_id = new_test.id
                
                upload_dir = Path("uploads/tests/cbc")
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                random_id = uuid.uuid4().hex[:8]
                filename = f"cbc_manual_{timestamp}_{random_id}.csv"
                file_path = upload_dir / filename
                
                df_annotated.to_csv(file_path, index=False)
                
                test_file = TestFile(
                    test_id=new_test.id,
                    name=filename,
                    extension='.csv',
                    path=str(file_path),
                    type='output'
                )
                db.add(test_file)
                
                cbc_model.tests_count += 1
                
                db.commit()
            except Exception as db_error:
                db.rollback()
                return {
                    "success": False,
                    "message": f"Error saving test to database: {str(db_error)}"
                }
            
            return {
                "success": True,
                "message": "CBC analysis completed successfully!",
                "result": result_data,
                "notes": notes,
                "patient_id": patient_id,
                "uploaded_by_id": uploaded_by_id,
                "test_id": test_id
            }
            
        except ValueError as ve:
            if db:
                db.rollback()
            return {
                "success": False,
                "message": f"Validation error: {str(ve)}"
            }
        except Exception as e:
            if db:
                db.rollback()
            return {
                "success": False,
                "message": f"Error during CBC analysis: {str(e)}"
            }


# ==================== Image Analysis ====================

class BloodImageAnalysisService:
    """Service for blood microscope image analysis"""
    
    def __init__(self):
        self.model = None
        self._loaded = False
    
    def process_image_upload(
        self,
        file: UploadFile,
        patient_id: int,
        uploaded_by_id: int,
        description: str = "",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        try:
            if not file or not file.filename:
                return {
                    "success": False,
                    "message": "No file was selected."
                }
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in valid_extensions:
                return {
                    "success": False,
                    "message": f"Invalid file type. Supported: {', '.join(valid_extensions)}"
                }
            
            upload_dir = Path("uploads/tests/blood_cell")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_id = uuid.uuid4().hex[:8]
            filename = f"{timestamp}_{random_id}{file_extension}"
            file_path = upload_dir / filename
            
            contents = file.file.read()
            with open(file_path, "wb") as f:
                f.write(contents)
            
            if db:
                from app.database import Test, TestFile, Model
                
                image_model = db.query(Model).filter(Model.name == "Blood Cell Image Classification").first()
                if not image_model:
                    return {
                        "success": False,
                        "message": "Blood Cell Image Classification model not found."
                    }
                
                new_test = Test(
                    patient_id=patient_id,
                    model_id=image_model.id,
                    notes=description if description else "Blood cell image uploaded",
                    review_status='pending'
                )
                db.add(new_test)
                db.flush()
                
                test_file = TestFile(
                    test_id=new_test.id,
                    name=filename,
                    extension=file_extension,
                    path=str(file_path),
                    type='input'
                )
                db.add(test_file)
                
                image_model.tests_count += 1
                
                db.commit()
                
                return {
                    "success": True,
                    "message": "Blood cell image uploaded successfully!",
                    "test_id": new_test.id,
                    "file_path": str(file_path)
                }
            else:
                return {
                    "success": False,
                    "message": "Database session not provided"
                }
            
        except Exception as e:
            if db:
                db.rollback()
            return {
                "success": False,
                "message": f"Error uploading image: {str(e)}"
            }


# ==================== Service Instances ====================

cbc_prediction_service = CBCPredictionService()
blood_image_service = BloodImageAnalysisService()