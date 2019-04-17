from __future__ import print_function  # Python 2/3 compatibility
import math
import boto3
import json
import decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def getNumCars(lotname):
    dynamodb = boto3.resource("dynamodb", aws_access_key_id="AKIAIFYOEWMP7W4EPBHQ", aws_secret_access_key="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",
                              region_name='us-east-2', endpoint_url="https://dynamodb.us-east-2.amazonaws.com")

    table = dynamodb.Table('livelot')

    try:
        response = table.get_item(
            Key={
                'lotname': lotname
            }
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        numCars = response["Item"]['numcars']
        print("GetItem succeeded:")
        print(json.dumps(numCars, indent=4, cls=DecimalEncoder))
        return numCars


def updateCars(comingIn, comingOut, lotname):

    # get the current number of cars in the lot
    currNumCars = getNumCars(lotname)
    if(comingIn):
        currNumCars += 1
    elif(comingOut):
        currNumCars += 1

    dynamodb = boto3.resource("dynamodb", aws_access_key_id="AKIAIFYOEWMP7W4EPBHQ", aws_secret_access_key="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",
                              region_name='us-east-2', endpoint_url="https://dynamodb.us-east-2.amazonaws.com")

    table = dynamodb.Table('livelot')

    response = table.update_item(
        Key={
            'lotname': "StudentCenter"
        },
        UpdateExpression="set numcars = :r",
        ExpressionAttributeValues={
            ':r': currNumCars
        },
        ReturnValues="UPDATED_NEW"
    )


def calc_center(box_points):
    w, h = get_width_height(box_points)
    cx = box_points[0][0] + w / 2
    cy = box_points[0][1] + h / 2
    return cx, cy


def get_width_height(box_points):
    # box_points is in format (top_left, top_right, bottom_left, bottom_right)
    w = abs(box_points[0][0] - box_points[1][0])
    h = abs(box_points[2][1] - box_points[0][1])
    return w, h


def calc_area(box_points):
    w, h = get_width_height(box_points)
    return w * h


def get_box_points(top_left, bottom_right):
    top_right = (bottom_right[0], top_left[1])
    bottom_left = (top_left[0], bottom_right[1])
    return [top_left, top_right, bottom_left, bottom_right]


def get_vector(p1, p2):
    x1, y1 = p1
    x2, y2 = p2

    dx = x2 - x1
    dy = y2 - y1
    return (dx, dy)


class CarTracker:
    def __init__(self):
        self._tracked_frames = []
        self._num_of_frames_to_track = 25
        self._num_cars_in = 0
        self._num_cars_out = 0

    def process_frame(self, frame_number, output_array, output_count):
        print('I AM IN PROCESS FRAME')
        print("FOR FRAME ", frame_number)
        # print("Output for each object : ", output_array)
        # print("Output count for unique objects : ", output_count)
        # print("------------END OF A FRAME --------------")

        # Get the location of every object in this frame
        # add the detection box and detection class to the frame_object array
        this_frame_objects = []
        for i in range(0, output_count):
            this_frame_objects.append(
                (output_array['detection_boxes_' + str(i)], output_array['detection_classes_' + str(i)]))

        # When we have a sufficient number of frames, identify the objects in them
        self._tracked_frames.append(this_frame_objects)
        if len(self._tracked_frames) == self._num_of_frames_to_track:
            self.identify_objects()
            self._tracked_frames = []

    def find_object_in_frame(self, obj1, objs_in_frame):
        num_objs_in_frame = len(objs_in_frame)
        box_points_1 = get_box_points(obj1[0][0], obj1[0][1])
        obj1_center = calc_center(box_points_1)
        closest_obj = None
        closest_obj_dist = 10000
        print('NEW_CALL to FIND_OBJECT_IN_FRAME')
        print('obj1', obj1, 'objs_in_frame', objs_in_frame)
        for i in range(num_objs_in_frame):
            obj2 = objs_in_frame[i]
            box_points_2 = get_box_points(obj2[0][0], obj2[0][1])
            obj2_center = calc_center(box_points_2)
            dist = math.hypot(
                obj2_center[0] -
                obj1_center[0], obj2_center[1] - obj1_center[1]
            )

            # TODO there should probably be some sort of thresholding done here
            if dist < closest_obj_dist:
                closest_obj = obj2
                closest_obj_dist = dist

        # The current issue is that this is returning a None type so when the unit
        # vector is calculated in the identify_objects function, the box points are undefined
        print('closest obj', closest_obj)
        print('original object', obj1)
        if closest_obj is None:
            print('Object was NONE')
            print('closest obj', closest_obj)
            print('original object', obj1)
            return obj1
        return closest_obj

    def identify_objects(self):
        frame0 = self._tracked_frames.pop()

        object_to_frames = []

        for i, obj in enumerate(frame0):
            for frame in self._tracked_frames:
                closest_obj = self.find_object_in_frame(obj, frame)
                try:
                    object_to_frames[i].append(closest_obj)
                except IndexError:
                    object_to_frames.append([closest_obj])

        # Get unit vectors
        # this print statement shows that box points of objects are being added before the full
        # box_points are calculated. Also, there are None type objects being added to the
        # object_to_frames array
        # IT IS BROKEN HERE :)
        vectors = [
            get_vector(
                calc_center(
                    get_box_points(
                        path[0][0][0],
                        path[0][0][1])
                ),
                calc_center(
                    get_box_points(
                        path[0][-2][0],
                        path[0][-2][1]
                    )
                )
            )
            for path in object_to_frames
        ]

        # Find cars coming in/going out
        coming_in = []
        going_out = []
        for v in vectors:
            print(v)
            x, y = v
            m = math.sqrt(x**2 + y**2)
            print(m)
            if m > 500:
                print(
                    '***********************************************************************')
                if y > 0:
                    self._num_cars_out += 1
                    updateCars(False, True, "StudentCenter")
                    going_out.append(v)
                else:
                    self._num_cars_in += 1
                    updateCars(True, False, "StudentCenter")
                    coming_in.append(v)

        print("-" * 80)
#        print(f'Cars coming in: {len(coming_in)}')
#        print(f'Cars going out: {len(going_out)}')
#        print(f'Total cars in: {self._num_cars_in}')
#        print(f'Total cars out: {self._num_cars_out}')
        # print('OBJECTS THROUGH FRAMES')
        # for i, locations in enumerate(object_to_frames):
        #    print(f'Object {i}: {locations}')
        print("-" * 80)
