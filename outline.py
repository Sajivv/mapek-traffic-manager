import cityflow


def planner():
     pass

def heuristic():
    pass

def data_collector():
  # may be don't need it
    pass



if __name__=="__main__":


#    eng = cityflow.Engine(config_path, thread_num=1)

#    set_replay_file(replay_file)

#    set_random_seed(seed)

    # Instantiate other stuff

    config_path = "config.json"
    replay_file = "replay.txt"
    seed = 42

    eng = cityflow.Engine(config_path, thread_num=1)
    eng.set_replay_file(replay_file)
    eng.set_random_seed(seed)

    data = []

    for episode in range(1000):
        episode_data = []
        eng.reset()

        lights = eng.get_intersection_ids()

        for step in 1000:
            # Monitor
            count = get_vehicle_count()
            vehicles = get_vehicles(include_waiting=False)
            
            data_collector(count,vehicles) # add somekind of data


            # Analyze
            heuristic()
            # Plan
            planner()
            # Actions

            # for vehicle in vehicles:
            #     set_vehicle_speed(vehicle_id, speed)
            #     set_vehicle_route(vehicle_id, route)
                
            for sl in lights:
                set_sl_phase()

            eng.next_step()

        data.append(episode_data)
