from vpobede import Vpobede


if __name__ == '__main__':
    vpobede = Vpobede()
    print('Updating events from the website... ', end='', flush=True)
    result = vpobede.update_events(save_to_cache=False)
    if result:
        print('done.')
        print('Saving events to the cache... ', end='', flush=True)
        result = vpobede.save_to_cache()
        if result:
            print('done.')
        else:
            print('failed.')
    else:
        print('failed.')
