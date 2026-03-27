import cityflow


def planner():
     pass

def heuristic():
    pass

def data_collector():
  # may be don't need it
    pass



if __name__=="__main__":


    eng = cityflow.Engine(config_path, thread_num=1)

    set_replay_file(replay_file)

    set_random_seed(seed)

    # Instantiate other stuff

    data = list()

    for episode in 1000:

        episode_data = list()

        eng.reset()

        for vehicle in vehicles:
                set_vehicle_speed(vehicle_id, speed)
                set_vehicle_route(vehicle_id, route)

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
