import time
import random


def process_job(job_type: str, payload: dict) -> dict:
    """Simulated job processors. Each returns a result dict or raises to trigger failure."""
    if job_type == "send_email":
        time.sleep(0.05)
        return {"sent_to": payload.get("to"), "message_id": f"msg_{random.randint(1000, 9999)}"}

    elif job_type == "resize_image":
        time.sleep(0.2)
        if random.random() < 0.1:  # 10% artificial failure rate for testing
            raise ValueError("Image corrupt or unsupported format")
        return {"output_path": f"/processed/{payload.get('filename')}", "size": "800x600"}

    elif job_type == "generate_report":
        time.sleep(0.1)
        return {"report_id": f"rpt_{random.randint(1000, 9999)}", "rows": random.randint(100, 5000)}

    else:
        raise ValueError(f"Unknown job_type: {job_type}")
