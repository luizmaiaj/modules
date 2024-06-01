from Cocoa import NSData, NSURL
from Quartz import CIImage
from Vision import VNImageRequestHandler, VNRecognizeTextRequest

def perform_ocr(image_path):
    # Convert the image path to a NSURL
    image_url = NSURL.fileURLWithPath_(image_path)

    # Create a CIImage from the NSURL
    ci_image = CIImage.imageWithContentsOfURL_(image_url)

    # Create a VNImageRequestHandler with the CIImage
    request_handler = VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)

    # Create a VNRecognizeTextRequest
    request = VNRecognizeTextRequest.alloc().init()

    # Perform the text recognition request
    success, error = request_handler.performRequests_error_([request], None)
    if not success:
        print(f"Error: {error}")
        return

    # Get the results
    observations = request.results()
    ocr_text = []
    for observation in observations:
        # Each observation is a VNRecognizedTextObservation
        top_candidate = observation.topCandidates_(1)[0]
        ocr_text.append(top_candidate.string())

    return " ".join(ocr_text)

def perform_mem_ocr(image_data):
    # Convert the image data to an NSData object
    ns_data = NSData.dataWithBytes_length_(image_data, len(image_data))

    # Create a CIImage from the NSData
    ci_image = CIImage.imageWithData_(ns_data)

    # Create a VNImageRequestHandler with the CIImage
    request_handler = VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)

    # Create a VNRecognizeTextRequest
    request = VNRecognizeTextRequest.alloc().init()

    # Perform the text recognition request
    success, error = request_handler.performRequests_error_([request], None)
    if not success:
        print(f"Error: {error}")
        return None

    # Get the results
    observations = request.results()
    ocr_text = []
    for observation in observations:
        # Each observation is a VNRecognizedTextObservation
        top_candidate = observation.topCandidates_(1)[0]
        ocr_text.append(top_candidate.string())

    return " ".join(ocr_text)
