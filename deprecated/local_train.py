from roboflow import Roboflow
from ultralytics import YOLO

if __name__ == '__main__':
    # 1. Download the dataset you just labeled using the code Roboflow gave you
    rf = Roboflow(api_key="f9LciZ0kNeUQINC8HkbK")
    project = rf.workspace("cadens-workspace-8ewzl").project("mk11-vision")
    version = project.version(1)
    dataset = version.download("yolov11")

    ## 2. Load the pre-trained model
    model = YOLO("yolo11n.pt") 

    # 3. Train the model locally
    # We set workers=2 to ensure Windows handles the CPU multithreading safely
    results = model.train(
        data=f"{dataset.location}/data.yaml", 
        epochs=100, 
        imgsz=640, 
        device=0,
        workers=2 
    )

    print("Training complete! Your new weights are in 'runs/detect/train/weights/best.pt'")