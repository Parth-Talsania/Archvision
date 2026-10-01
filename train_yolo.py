"""
YOLOv8 Instance Segmentation Training Script
=============================================
Purpose: Train a custom YOLOv8-Seg model to detect rooms in floor plan images.

Prerequisites:
    pip install ultralytics

Usage:
    python train_yolo.py
    
    Or with custom dataset path:
    python train_yolo.py --data /path/to/data.yaml
"""

import argparse
from pathlib import Path
from ultralytics import YOLO


def train_model(
    data_yaml: str,
    model_size: str = "small",
    imgsz: int = 1024,
    epochs: int = 120,
    batch: int = 16,
    project: str = "runs/segment",
    name: str = "floor_plan_rooms"
):
    """
    Train YOLOv8 Instance Segmentation model.
    
    Args:
        data_yaml: Path to the Roboflow-exported data.yaml file
        model_size: 'nano' (yolov8n-seg) or 'small' (yolov8s-seg)
        imgsz: Image size for training (640 or 1024 for high-res plans)
        epochs: Number of training epochs
        batch: Batch size (reduce if GPU OOM)
        project: Output directory for training runs
        name: Name for this training run
    
    Returns:
        Path to the best model weights
    """
    
    # =========================================================================
    # MODEL SELECTION
    # =========================================================================
    # Why 'Small' (yolov8s-seg) is recommended for floor plans:
    # 
    # 1. FLOOR PLANS HAVE FINE DETAILS: Room boundaries, thin walls, and small 
    #    text require more feature extraction capacity than 'Nano' provides.
    #
    # 2. DATASET IS SMALL (~80-240 images): A slightly larger model can learn
    #    more robust features without severe overfitting, especially with 
    #    augmentation.
    #
    # 3. INFERENCE SPEED IS NOT CRITICAL: Unlike real-time video, floor plan
    #    processing is batch/offline work. The extra 10-20ms per image is fine.
    #
    # 4. POLYGON PRECISION MATTERS: 'Small' produces more accurate mask 
    #    boundaries, which is crucial for calculating room areas.
    # =========================================================================
    
    model_map = {
        "nano": "yolov8n-seg.pt",   # Fastest, least accurate
        "small": "yolov8s-seg.pt",  # Recommended balance for floor plans
        "medium": "yolov8m-seg.pt", # If you have more data/GPU memory
    }
    
    base_model = model_map.get(model_size, "yolov8s-seg.pt")
    print(f"\n{'='*60}")
    print(f"Loading base model: {base_model}")
    print(f"{'='*60}\n")
    
    # Load the pretrained model (transfer learning)
    model = YOLO(base_model)
    
    # =========================================================================
    # TRAINING CONFIGURATION
    # =========================================================================
    # Key hyperparameters explained:
    #
    # imgsz=640:  Standard size. Use 1024 if your floor plans are high-res
    #             and you have GPU memory (increases accuracy but slower).
    #
    # epochs=100: For small datasets, more epochs help the model converge.
    #             The training will auto-stop if no improvement (patience).
    #
    # batch=16:   Adjust based on GPU memory:
    #             - 4GB VRAM: batch=4-8
    #             - 8GB VRAM: batch=8-16
    #             - 16GB+ VRAM: batch=16-32
    #
    # patience=20: Early stopping - stops if validation loss doesn't improve
    #              for 20 epochs (prevents overfitting).
    #
    # augment=True: Enables built-in augmentation (mosaic, mixup, etc.)
    #               ON TOP of Roboflow augmentations.
    # =========================================================================
    
    results = model.train(
        data=data_yaml,
        imgsz=imgsz,
        epochs=epochs,
        batch=batch,
        project=project,
        name=name,
        
        # Optimization
        patience=20,          # Early stopping patience
        save=True,            # Save checkpoints
        save_period=10,       # Save every 10 epochs
        
        # Augmentation (additional to Roboflow)
        augment=True,
        hsv_h=0.015,          # Hue augmentation
        hsv_s=0.7,            # Saturation augmentation
        hsv_v=0.4,            # Value/brightness augmentation
        degrees=10.0,         # Rotation augmentation (+/- degrees)
        translate=0.1,        # Translation augmentation
        scale=0.5,            # Scale augmentation
        fliplr=0.5,           # Horizontal flip probability
        flipud=0.0,           # Vertical flip (usually 0 for floor plans)
        mosaic=1.0,           # Mosaic augmentation
        
        # Performance
        workers=8,            # Data loading workers
        device=None,          # Auto-detect GPU/CPU
        amp=True,             # Automatic Mixed Precision (faster training)
        
        # Visualization
        plots=True,           # Generate training plots
        val=True,             # Run validation during training
    )
    
    # =========================================================================
    # OUTPUT
    # =========================================================================
    best_model_path = Path(project) / name / "weights" / "best.pt"
    last_model_path = Path(project) / name / "weights" / "last.pt"
    
    print(f"\n{'='*60}")
    print("TRAINING COMPLETE!")
    print(f"{'='*60}")
    print(f"\nBest model saved to: {best_model_path}")
    print(f"Last model saved to: {last_model_path}")
    print(f"\nTraining metrics and plots saved to: {Path(project) / name}")
    print("\nNext steps:")
    print("  1. Check runs/segment/floor_plan_rooms/ for training curves")
    print("  2. Use best.pt for inference in your pipeline")
    print(f"{'='*60}\n")
    
    return best_model_path


def is_notebook():
    """Detect if running in a Jupyter/Colab/Kaggle notebook."""
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            return True
    except ImportError:
        pass
    return False


def main(
    data: str = None,
    model: str = "small",
    imgsz: int = 640,
    epochs: int = 100,
    batch: int = 16
):
    """
    Main entry point - works in both notebooks and command line.
    
    For Notebooks (Colab/Kaggle):
        main(data="/path/to/data.yaml")
    
    For Command Line:
        python train_yolo.py --data /path/to/data.yaml
    """
    
    # If running in notebook, use function arguments directly
    if is_notebook():
        if data is None:
            print("\n" + "="*60)
            print("NOTEBOOK MODE DETECTED")
            print("="*60)
            print("\nUsage in notebook cell:")
            print('  main(data="/kaggle/working/YOUR_DATASET/data.yaml")')
            print("\nOr call train_model() directly:")
            print('  train_model(data_yaml="/path/to/data.yaml")')
            print("="*60 + "\n")
            return
        
        data_yaml = data
        model_size = model
        img_size = imgsz
        num_epochs = epochs
        batch_size = batch
    else:
        # Command-line mode: use argparse
        parser = argparse.ArgumentParser(
            description="Train YOLOv8 Instance Segmentation for Floor Plan Rooms"
        )
        parser.add_argument(
            "--data", 
            type=str, 
            default="dataset/data.yaml",
            help="Path to Roboflow-exported data.yaml file"
        )
        parser.add_argument(
            "--model", 
            type=str, 
            default="small",
            choices=["nano", "small", "medium"],
            help="Model size: nano (fast), small (recommended), medium (accurate)"
        )
        parser.add_argument(
            "--imgsz", 
            type=int, 
            default=640,
            help="Image size for training (640 or 1024)"
        )
        parser.add_argument(
            "--epochs", 
            type=int, 
            default=100,
            help="Number of training epochs"
        )
        parser.add_argument(
            "--batch", 
            type=int, 
            default=16,
            help="Batch size (reduce if GPU OOM error)"
        )
        
        args = parser.parse_args()
        data_yaml = args.data
        model_size = args.model
        img_size = args.imgsz
        num_epochs = args.epochs
        batch_size = args.batch
    
    # Validate data.yaml exists
    if not Path(data_yaml).exists():
        print(f"\nERROR: data.yaml not found at: {data_yaml}")
        print("\nMake sure you:")
        print("  1. Exported your Roboflow dataset in YOLOv8 format")
        print("  2. Extracted the zip to a 'dataset/' folder")
        print("  3. The data.yaml file is at the specified path")
        print("\nExample folder structure:")
        print("  dataset/")
        print("  ├── data.yaml")
        print("  ├── train/")
        print("  │   ├── images/")
        print("  │   └── labels/")
        print("  └── valid/")
        return
    
    # Start training
    train_model(
        data_yaml=data_yaml,
        model_size=model_size,
        imgsz=img_size,
        epochs=num_epochs,
        batch=batch_size
    )


if __name__ == "__main__":
    main()
