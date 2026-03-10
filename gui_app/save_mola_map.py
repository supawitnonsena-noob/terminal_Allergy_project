import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2
import sensor_msgs_py.point_cloud2 as pc2
import open3d as o3d
import numpy as np
import matplotlib.pyplot as plt
import sys
import os
import argparse

TOPIC_NAME = '/lidar_odometry/localmap_points'  

class MapSaver(Node):
    def __init__(self, file_prefix, save_path):
        super().__init__('map_saver_node')
        
        self.file_prefix = file_prefix
        self.save_path = save_path
        
        qos_profile = QoSProfile(
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        self.get_logger().info(f'Waiting for map data from: {TOPIC_NAME} ...')
        
        self.subscription = self.create_subscription(
            PointCloud2,
            TOPIC_NAME,
            self.listener_callback,
            qos_profile
        )

    def listener_callback(self, msg):
        self.get_logger().info(f'Received map! Processing {msg.width * msg.height} points...')
        
        gen = pc2.read_points(msg, field_names=['x', 'y', 'z'], skip_nans=True)
        raw_list = list(gen)
        
        if not raw_list:
            self.get_logger().error("Map is empty!")
            return

        dtype_list = [('x', np.float32), ('y', np.float32), ('z', np.float32)]
        structured_arr = np.array(raw_list, dtype=dtype_list)
        
        x = structured_arr['x']
        y = structured_arr['y']
        z = structured_arr['z']
        
        points = np.column_stack((x, y, z))

        full_pcd_path = os.path.join(self.save_path, f'{self.file_prefix}.pcd')
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        o3d.io.write_point_cloud(full_pcd_path, pcd)
        self.get_logger().info(f'Saved 3D Map to: {full_pcd_path}')

        self.convert_to_pgm(points, full_pcd_path)
        
        self.get_logger().info('Mission Complete. Shutting down...')
        rclpy.shutdown()
        sys.exit(0)

    def convert_to_pgm(self, points, pcd_path):
        self.get_logger().info('Converting to 2D Map (.pgm) ...')
        
        z_min = 0.2    
        z_max = 1.5    
        resolution = 0.05 
        
        mask = (points[:, 2] > z_min) & (points[:, 2] < z_max)
        sliced_points = points[mask]

        if len(sliced_points) == 0:
            self.get_logger().warn("No points found in height range! Cannot save PGM.")
            return

        x_points = sliced_points[:, 0]
        y_points = sliced_points[:, 1]

        min_x, max_x = np.min(x_points), np.max(x_points)
        min_y, max_y = np.min(y_points), np.max(y_points)

        width = int(np.ceil((max_x - min_x) / resolution)) + 1
        height = int(np.ceil((max_y - min_y) / resolution)) + 1

        img_grid = np.ones((height, width), dtype=np.uint8) * 255 

        for x, y in zip(x_points, y_points):
            ix = int((x - min_x) / resolution)
            iy = int((y - min_y) / resolution)
            
            if 0 <= ix < width and 0 <= iy < height:
                img_grid[height - 1 - iy, ix] = 0 

        pgm_path = pcd_path.replace('.pcd', '.pgm')
        plt.imsave(pgm_path, img_grid, cmap='gray', vmin=0, vmax=255)
        self.get_logger().info(f'Saved 2D Image to: {pgm_path}')

        yaml_content = f"""image: {os.path.basename(pgm_path)}\nresolution: {resolution}\norigin: [{min_x}, {min_y}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n"""
        yaml_path = pcd_path.replace('.pcd', '.yaml')
        with open(yaml_path, "w") as f:
            f.write(yaml_content)
        self.get_logger().info(f'Saved Config to: {yaml_path}')

def main(args=None):
    # รองรับการรับ Argument จาก GUI
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='mola_map')
    parser.add_argument('--path', default='.')
    parsed_args, unknown = parser.parse_known_args()

    rclpy.init(args=args)
    node = MapSaver(parsed_args.name, parsed_args.path)
    
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()